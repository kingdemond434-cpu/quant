"""Fail-closed bridge from canonical ten-gate certificates to shadow work."""
from __future__ import annotations

import json
import re
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
    # PARTIAL READABILITY IS UNMEASURED, NOT A COUNT (L1.28a / WS-005). This read `any(...)`,
    # so one readable source was enough to publish a confident number while the other was
    # unreadable. Measured 2026-09-11 on a live clone:
    #
    #     unreachable_certified {'n': 0, 'sources_readable':
    #                            {'QQUANT_GATES': True, 'REAL_SURVIVORS': False}}
    #
    # A clean zero, standing for "nothing is blocked", derived from half the evidence -- and
    # "nothing is blocked" and "I could not read the certificates" are opposite facts. The fence
    # written to catch exactly that confusion had it in its own return line.
    #
    # `all` is the honest test: every source must be readable before the count means anything.
    # A count over a subset of the sources is a count of that subset, not of the desk.
    return {"n": len(blocked) if all(readable.values()) else None,
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

#: `power_cure_specs` STOOD HERE AND IS DELETED (principal 2026-09-24, "delete the other").
#: It was the five-tuple twin of the power-cure lane removed from `authorized_runs`, admitting
#: validity-pass / power-DEFICIENT cells as though they were certified. It had NO CALLERS on any
#: tree -- which is the condition this module's own `run_key` docstring names as the dangerous
#: one: "an orphaned function is not harmless; it is a wrong answer waiting for its first
#: caller". Its answer was wrong: 0 of 1,240 eligible cure cells pass all ten gates and every
#: one of them fails `deflated_sharpe`. One canonical lane, and the other stops existing.




#: Certificates that passed all ten gates and were still dropped before enrolment, with the
#: reason. Reset at the start of every `authorized_runs` call so it always describes the LAST
#: pass rather than accumulating across a long-lived process.
#:
#: Exposed as module state, not just printed, because the two readers need different things: the
#: shadow log needs a line a human greps at 3am, and `same_day_enrolment` needs to be able to say
#: WHY a certificate it is flagging has no clock instead of only that it has none.
DROPPED_CERTIFICATES: list[dict[str, str]] = []

#: Certificates `certificate_hygiene` already EVICTED from the sealed canon as unrunnable (their
#: `params` were never recorded and are never guessed). They still stand in the judge's report --
#: eviction is not revocation -- so without this every pass re-announced the same six as fresh
#: ENROL-GAP drops (measured 2026-09-30: five session_range_breakout rows and one AUDNZD
#: dav_range_filter_adx, all gated 2026-08-23), which buried real drops and read as a live defect.
#: Listed here instead, by key, so the eviction stays visible without posing as a new finding.
EVICTED_CERTIFICATES: list[str] = []


def _evicted_keys(base: Path) -> set[str]:
    """Keys the sealed canon records as evicted-unrunnable. Absent or unreadable -> empty set, so
    a missing record can only make the door LOUDER (every drop reported), never quieter."""
    ev = _read(base / "data" / "UNIVERSAL_SURVIVORS.canon.json").get("unrunnable_evicted")
    return {str(k) for k in ev} if isinstance(ev, list) else set()


#: Families whose cell, once MOVED to another instrument with its donor's params, tests a rule
#: nobody wrote. Mirrors `hypothesis_families.MOVED_CELL_FAMILIES` (a test pins the two equal);
#: restated because this module is imported by the forward engine and must stay import-light.
#: `carry` and `event_reaction` are absent on purpose: the judge supplies the row's instrument
#: for both, so a stale name there changed nothing that ran.
MOVED_CELL_FAMILIES = frozenset({"entry_conditioned", "carry_risk_off", "forced_flow"})
#: Certificates refused this pass as VOID_MOVED_CELL, by name (also in DROPPED_CERTIFICATES).
VOID_MOVED_CERTIFICATES: list[str] = []
#: entry_conditioned certificates naming another instrument whose BASE family could not be shown
#: to read `symbol`: left enrolled (an honest certificate is not refused on a guess), by name.
UNPROVEN_ENTRY_CONDITIONED: list[str] = []


def _base_reads_symbol(base_family: str) -> bool | None:
    """Does `base_family`'s constructor take `symbol`? None when it cannot be resolved."""
    try:
        import inspect

        from mt5desk.families import get_family_func
        fn = get_family_func(str(base_family))
        return None if fn is None else "symbol" in inspect.signature(fn).parameters
    except Exception:
        return None


def void_moved_cell(row: dict, spec: dict, params: dict) -> str | None:
    """The reason a certificate is VOID_MOVED_CELL, or None. `"UNPROVEN"` is returned for an
    entry_conditioned certificate whose base family is not shown to read `symbol`: the caller
    names it and ENROLS it.

    Box 2026-11-10: two carry_risk_off certificates (GBPSEK and NOKSEK) passed all ten gates
    with `params.symbol: USDSGD` -- a cell carried to another instrument with its donor's
    params, so the family traded one instrument's bars on ANOTHER's carry side and swap terms.
    The mechanism the certificate states (gate one) is not the rule that was run. The certificate
    is kept and named, and it does not advance; the corrected cell is judged as a new trial by
    the docket's moved-cell repair and earns its own certificate or does not. Decided from the
    row alone, so it needs no join and cannot go stale.

    entry_conditioned only forwards `symbol` to its base family, and only a base that takes one
    reads it (`families_specialist.family_entry_conditioned`). So it is refused only where the
    base family's own signature has `symbol`; anything else ran the rule its certificate states
    and stays enrolled."""
    family = str(spec.get("family") or row.get("family") or "")
    if family not in MOVED_CELL_FAMILIES:
        return None
    sym = str(spec.get("symbol") or row.get("sym") or row.get("symbol") or "").strip().upper()
    named = params.get("symbol")
    if isinstance(named, list) and len(named) == 1:
        named = named[0]
    named = named.strip().upper() if isinstance(named, str) else ""
    if not sym or not named or named == sym:
        return None
    if family == "entry_conditioned":
        base = str(params.get("base_family") or "")
        if _base_reads_symbol(base) is not True:
            return "UNPROVEN"
        family = f"entry_conditioned[{base}]"
    return (f"VOID_MOVED_CELL: a {family} certificate on {sym} whose params name {named} as the "
            f"traded instrument -- it was judged on {sym}'s bars with {named}'s terms, a rule "
            f"nobody wrote. Kept and named, not enrolled; the corrected cell is re-judged as a "
            f"new trial (data/hypotheses/moved_cell_void.json)")


def void_moved_certificates(base: Path = BASE) -> dict:
    """DRY RUN: every ten-gate certificate the VOID_MOVED_CELL door refuses on the canon as it
    stands, and every entry_conditioned one it leaves enrolled as unproven. Reads only."""
    universal, source = _canon(base)
    refused, unproven = [], []
    for name, row in (universal.get("survivors") or {}).items():
        if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
            continue
        spec = row.get("shadow_spec")
        params = spec.get("params") if isinstance(spec, dict) else None
        if not isinstance(params, dict):
            continue
        why = void_moved_cell(row, spec, params)
        if why == "UNPROVEN":
            unproven.append(str(name))
        elif why:
            refused.append({"certificate": str(name), "family": str(spec.get("family") or ""),
                            "symbol": str(spec.get("symbol") or row.get("sym") or ""),
                            "named": params.get("symbol"), "why": why})
    return {"source": source, "refused": refused, "n_refused": len(refused),
            "unproven_entry_conditioned": unproven}


#: Params a family's replay never reads (the judge supplies the row's own instrument), so two
#: certificates differing only there are ONE executable. Mirrors
#: `hypothesis_families.EXECUTABLE_UNREAD` (a test pins the two equal); restated to stay
#: import-light.
EXECUTABLE_UNREAD: dict[str, frozenset[str]] = {"carry": frozenset({"input_symbol", "symbol"})}
#: This pass's executables held by more than one certificate: which copy keeps the clock, which
#: copies were not enrolled, and which surplus copies already had a clock and were left running.
EXECUTABLE_COPIES: list[dict] = []


def one_clock_per_executable_enforced() -> bool:
    """False under QUANT_ONE_CLOCK_PER_EXECUTABLE=0: copies are counted and all enrolled."""
    import os
    return os.environ.get("QUANT_ONE_CLOCK_PER_EXECUTABLE", "1").strip() != "0"


#: certificate name -> the (chart, timeframe, session) its `shadow_spec` states outside params,
#: each kept apart so a chart can never stand in for a session; filled by
#: `authorized_runs` each pass (the run row itself has never carried it).
_SPEC_CHART: dict[str, str] = {}
_NAME_CHART = re.compile(r"@([A-Za-z]{1,3}\d{1,3})\b")


def _executable_of(run: dict) -> str | None:
    """EVERY DIMENSION THE RUN CARRIES IS IN THE KEY (chart on the row, in the spec or in the
    certificate's own name; session; lane): an @M15 carry certificate beside an H1 one is a
    different rule. An extra dimension can only keep a copy enrolled."""
    unread = EXECUTABLE_UNREAD.get(str(run.get("family") or ""))
    if unread is None or run.get("lane") == "scalp":
        return None
    params = {k: v for k, v in (run.get("params") or {}).items() if k not in unread}
    name = str(run.get("certificate") or "")
    named = _NAME_CHART.search(name)
    return json.dumps([str(run.get("symbol") or "").upper(), run.get("family"),
                       run.get("selector"), run.get("condition"), run.get("side"), params,
                       run.get("timeframe"), run.get("chart"), run.get("session"),
                       run.get("lane"), _SPEC_CHART.get(name),
                       named.group(1).upper() if named else None],
                      sort_keys=True, default=str)


def _clocked(base: Path) -> tuple[list[tuple[str, str, dict, str, str]], dict[str, str]]:
    """Every forward clock in the registry, twice: (symbol, family, params, chart, forward_start)
    rows for the generous match, and {registry key: forward_start} for the exact one. An
    unreadable registry is an empty answer, which keeps every copy."""
    out: list[tuple[str, str, dict, str, str]] = []
    keys: dict[str, str] = {}
    rows = _read(base / "data" / "sleeve_registry.json").get("sleeves")
    items = list(rows.items()) if isinstance(rows, dict) else [
        (str(r.get("key") or ""), r) for r in (rows if isinstance(rows, list) else ())
        if isinstance(r, dict)]
    for key, r in items:
        ident = r.get("identity") if isinstance(r, dict) else None
        if not isinstance(ident, dict):
            continue
        params = ident.get("params") if isinstance(ident.get("params"), dict) else {}
        st = str(r.get("forward_start") or r.get("frozen_at") or "9999")
        out.append((str(ident.get("symbol") or "").upper(), str(ident.get("family") or ""),
                    params, str(ident.get("timeframe") or "").upper(), st))
        if key:
            keys[str(key)] = st
    return out, keys


def _engine_key(run: dict) -> str | None:
    """The registry key the ENROLMENT path would write for this run, from the engine's own
    builder. None when the engine cannot be imported here; the generous match still answers."""
    try:
        return run_key(run)
    except Exception:
        return None


def one_clock_per_executable(runs: list[dict], base: Path = BASE, *,
                             enforce: bool | None = None,
                             registry_readable: bool | None = None) -> list[dict]:
    """One forward clock per canonical executable (box 2026-11-10: 21 carry clocks in the
    registry were a handful of carry rules, each certified several times under a foreign
    `input_symbol` the replay never reads).

    NOTHING THAT HAS A CLOCK LOSES IT. A copy that already holds a registry clock is always
    returned, so no accrued forward evidence is orphaned; such surplus clocks are only named.
    A copy with NO clock is withheld only when another copy of the same executable is returned
    in this same pass -- the executable is being forward-tested either way, on identical
    signals, so nothing is forgone. A copy whose engine key is a registry row, or equals the
    keeper's key, is never withheld. The keeper is the copy with the earliest clock, else the
    one whose unread params name its own instrument, else the first by certificate name. If the
    registry cannot be read nothing is withheld."""
    EXECUTABLE_COPIES.clear()
    enforce = one_clock_per_executable_enforced() if enforce is None else enforce
    if registry_readable is None:
        registry_readable = (base / "data" / "sleeve_registry.json").exists()
    groups: dict[str, list[dict]] = {}
    for run in runs:
        k = _executable_of(run)
        if k is not None:
            groups.setdefault(k, []).append(run)
    if not any(len(g) > 1 for g in groups.values()):
        return runs
    clocked, by_key = _clocked(base) if registry_readable else ([], {})

    def start(run: dict) -> str | None:
        # A CLOCK IS RECOGNISED TWICE OVER, and either is enough.
        # (1) EXACTLY: the key the engine would write for this run is a registry row. Box
        #     2026-11-10: external.CHFNOK.carry.p=b56bcfef9a4a010c states timeframe=H1, the
        #     engine's key drops it, and its key CHFNOK.carry.asia#input_symbol=CHFNOK was a
        #     running clock with 46 observations that rule (2) alone did not recognise.
        # (2) GENEROUSLY: same instrument and family, and every param the certificate states is
        #     on the clock's identity (which may carry more); `timeframe` is read against the
        #     identity's own chart, where the registry keeps it.
        # Erring either way can only keep a copy enrolled, never take a clock's certificate away.
        key = _engine_key(run)
        exact = by_key.get(key) if key else None
        sym, fam = str(run.get("symbol") or "").upper(), str(run.get("family") or "")
        mine = dict(run.get("params") or {})
        chart = str(mine.pop("timeframe", "") or "").upper()
        starts = [st for s_, f_, p_, tf_, st in clocked
                  if s_ == sym and f_ == fam and all(p_.get(k) == v for k, v in mine.items())
                  and (not chart or chart == (tf_ or "H1")
                       or str(p_.get("timeframe") or "").upper() == chart)]
        if exact:
            starts.append(exact)
        return min(starts) if starts else None

    def own(run: dict) -> bool:
        sym = str(run.get("symbol") or "").upper()
        unread = EXECUTABLE_UNREAD[str(run.get("family"))]
        return all(str(v).upper() == sym for k, v in (run.get("params") or {}).items()
                   if k in unread)

    withheld: set[int] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=lambda r: (start(r) or "9999", not own(r),
                                              str(r.get("certificate"))))
        keeper, rest = ranked[0], ranked[1:]
        # A copy whose engine key IS the keeper's key is not a second clock at all: the two
        # certificates enrol onto one registry row. It is always returned and only named.
        k_key = _engine_key(keeper)
        same = [r for r in rest if k_key is not None and _engine_key(r) == k_key]
        rest = [r for r in rest if all(r is not x for x in same)]
        left = [str(r.get("certificate")) for r in rest if start(r)]
        new = [r for r in rest if not start(r)]
        act = enforce and registry_readable
        EXECUTABLE_COPIES.append({
            "symbol": keeper.get("symbol"), "family": keeper.get("family"),
            "copies": len(group), "keeps_clock": str(keeper.get("certificate")),
            "keeper_names_its_own_instrument": own(keeper),
            "surplus_clocks_left_running": left,
            "sharing_keepers_key": [str(r.get("certificate")) for r in same],
            "not_enrolled": [str(r.get("certificate")) for r in new] if act else [],
            "would_not_enrol": [] if act else [str(r.get("certificate")) for r in new]})
        if act:
            for r in new:
                withheld.add(id(r))
                _drop(r.get("certificate"),
                      f"EXECUTABLE_COPY: the same executable as {keeper.get('certificate')} "
                      f"(a {keeper.get('family')} rule on {keeper.get('symbol')}; the params "
                      f"that differ are never read by its replay), which keeps the clock")
    return [r for r in runs if id(r) not in withheld]


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


#: THE POWER-CURE LANE IS DELETED. It used to live here as `CURE_BUDGET = 120`, and this comment
#: is its headstone rather than its documentation -- kept only so the next session recognises the
#: shape and does not reinvent it for a third time.
#:
#: THE PRINCIPAL'S ORDER, 2026-09-23 and restated 2026-09-24: "allow evidence only if they pass
#: the 10 gates and are certificates, otherwise there is no point. No power-cure lane, no
#: validity-pass enrolment, no lane self-declaring its way onto a clock" -- then, on the split
#: this lane created: "all certis clocks must be one canonised lane not seperate ... if the 148
#: really are certificates then make them canon, stop, delete the other, and unify the whole
#: pipeline."
#:
#: SO THE QUESTION WAS SETTLED BY MEASUREMENT, NOT BY PREFERENCE (2026-09-24, trading box):
#:     canon survivors                      28, of which all_ten_pass  28/28
#:     cure candidates eligible          1,240, of which all_ten_pass   0/1,240
#:     failed_power_gates over those 1,240: deflated_sharpe 1,240, cpcv 54,
#:                                          expected_value 41, in_sample_screen 41,
#:                                          walk_forward 14
#: EVERY eligible cure row fails `deflated_sharpe` -- the multiple-testing charge, which is the
#: one gate whose entire purpose is to stop a wide search from minting false positives. A lane
#: that enrolled 120 of them and called them certificates was not curing the charge; it was
#: running the exact search the charge exists to price, and then reporting the result under the
#: word "certificate". `forward_enrolment` published `n_certificates: 148` on that basis, and 120
#: of those 148 had passed no ten-gate attestation at any point in their lives.
#:
#: WHAT REPLACES IT: nothing. A power-deficient cell is re-judged by the gauntlet when its cell
#: comes up; `reports/POWER_CURE_CANDIDATES.json` is still written by the sealed writer and is
#: still honest EVIDENCE about which cells are close, but it confers no clock and no authority.
#: The relief valve for a cell that cannot pass on its history is MORE HISTORY or a better
#: hypothesis, never a forward clock issued on the strength of having nearly passed.
#:
#: AND THIS IS NOT A RESTRAINT (Rule 1, growth governance). Forward clocks deploy no capital, so
#: deleting 120 of them lowers no risk and forgoes no bet. It RAISES the desk's throughput: the
#: 120 were in the same multiplicity cohort as the 28 real certificates, so every one of them was
#: making the bar harder for a certificate that had actually earned its place.


def authorized_runs(base: Path = BASE,
                    lanes: tuple[str, ...] = ("h1", "scalp")) -> list[dict]:
    """Exactly-specified RUNNABLE certificates: symbol, selector, family AND certified params.

    EVERY ROW THIS RETURNS HOLDS A TEN-GATE CERTIFICATE IN THE CANONICAL STORE. That is now the
    whole contract, and it is what makes `len(authorized_runs())` a certificate count rather than
    a roster size -- the two were the same word and different numbers (148 against 28) until the
    power-cure lane was deleted above, and a caller may once again read this length as "how many
    certificates does the desk hold".

    `lanes` names which engines' rows to return. H1 rows are what `shadow_forward` enrols; scalp
    rows (`scalp.*` keys, `exec == "scalp_market"`) carry the recipe `mt5desk.scalp_exec` trades
    and belong to `scalp_shadow`'s clock. Both come from the SAME canonical store and both are
    certificates; an H1-only consumer passes `lanes=("h1",)`, or skips rows whose `exec` names an
    executor it is not.

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
    EVICTED_CERTIFICATES.clear()
    VOID_MOVED_CERTIFICATES.clear()
    UNPROVEN_ENTRY_CONDITIONED.clear()
    _SPEC_CHART.clear()
    universal, canon_from = _canon(base)
    evicted = _evicted_keys(base)
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
        if str(name) in evicted and not (isinstance(spec, dict)
                                         and isinstance(spec.get("params"), dict)):
            EVICTED_CERTIFICATES.append(str(name))   # already evicted and still unrunnable
            continue
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
        _SPEC_CHART[str(name)] = json.dumps([spec.get("chart"), spec.get("timeframe"),
                                             spec.get("session")], default=str)
        void = void_moved_cell(row, spec, params)
        if void == "UNPROVEN":
            UNPROVEN_ENTRY_CONDITIONED.append(str(name))      # named, and enrolled
        elif void:
            VOID_MOVED_CERTIFICATES.append(str(name))
            _drop(name, void)
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
    # THE POWER-CURE LANE STOOD HERE AND IS DELETED (principal 2026-09-24: "delete the other,
    # and unify the whole pipeline"). It read `reports/POWER_CURE_CANDIDATES.json` and appended
    # up to CURE_BUDGET=120 validity-pass, power-DEFICIENT cells to this list carrying
    # `promotion_authority: False`. They were not certificates -- 0 of 1,240 passed all ten
    # gates, all 1,240 failed `deflated_sharpe` -- but every organ downstream counted the length
    # of this list and called the answer "certificates". The headstone above `authorized_runs`
    # carries the measurement. One lane, one number: this function returns certificates only.
    runs = one_clock_per_executable(runs, base)
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
