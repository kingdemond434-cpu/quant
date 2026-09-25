#!/usr/bin/env python3
"""EXCITATION FENCE (L1.45) -- the desk explores in research and must explore in EXECUTION too.

WHICH EXECUTOR. THE MT5 GATEWAY, from 2026-09-23. This fence was written against the Binance
cash-and-carry executor and until today it still read that desk's files: the denylist from
`web/trade_forensics.json`, whose only producer `scripts/run_trade_forensics.py` is a crypto organ
that reads Binance testnet commission events and has never written that artifact on this box
(max_audit: "web/trade_forensics.json MISSING -- daily trade-class bleed analysis has never
produced output"); the tape from `data/moat/execution_tape/cashcarry_trades.jsonl`, absent; the
design from `data/excitation_design.json`, whose arms are `maker_wait_s` on a Binance post-only
quote and whose cells are keyed AAVEUSDT/BTCUSDT; and the wiring marker from
`scripts/run_cashcarry_executor.py`, DELETED 2026-09-05. So the fence reported UNMEASURED on an
unreadable crypto denylist forever, and the one thing it could not do was look at the executor
this desk actually runs.

L1.45 did not retire with that desk. The MT5 gateway (`desks/mt5/mt5desk/gateway.py`) sends live
orders every ten minutes and is a CERTAINTY-EQUIVALENCE controller of exactly the kind this law is
about: `mt5desk/execution_policy.py` prices nine execution policies and `mt5desk/execution_registry
.py` five child-order algorithms on EVERY pass, the winner is written onto the intent row as
`policy_advice`, and a hard-coded branch then sends the same order shape it always sends. The
ranking exists, is measured, and decides nothing. This fence now reads that executor's own
artifacts.

WHY THIS FENCE EXISTS. Every other checker on this desk walks NODES and EDGES: check_orphan_code
walks the import graph, check_money_path_wired asks whether a thing has a caller, check_freshness
contracts producer->consumer age, run_reality_gap compares adjacent links. NOTHING LOOKS FOR
CYCLES. The defect this fence names lives only in a cycle, and every file in it is individually
correct (verified 2026-08-01):

    traded -> recorded -> measured -> cheap -> traded

An unmeasured symbol needs ~4x the funding of a measured one to clear `_entry_gate`, so it is
never traded; the recorder's universe is the traded set, so it is never recorded; the cost model
walks only recorded symbols, so it is never measured. The set is ABSORBING: once out, no path
back, forever. The fail-closed default that welds it is GOOD engineering in isolation -- its
COMPOSITION with the recorder's universe is the defect, and no single-file review can see it.

FENCE STATUS (exit 2 on the first four -- a gate, not a report):
  NO-DATA        design artifact absent or unreadable -- the experiment cannot run.
  NO-EXCITATION  epsilon=0, cap=0, or the budget has gone unspent while the book traded.
                 An unspent declared budget is an IDLENESS defect (L1.28a), never prudence.
  UNMEASURED     the denylist inputs could not be read, so WHO IS BLOCKED is unknown and the
                 ABSORBING question below cannot be asked at all (L1.55/L1.28a). See the
                 provenance note on `_bleeding_symbols`.
  ABSORBING      an execution exclusion with NO PATH BACK -- a denylisted symbol whose `n` is
                 frozen by the very block that denylisted it (L1.16a: every kill records its
                 re-entry condition; the alpha graveyard has that discipline, the EXECUTION
                 graveyard had none).
  UNIDENTIFIED   arms configured but zero randomised observations, or design cells still empty.
                 A cell with n_observed=0 reports UNIDENTIFIED and NEVER a prior.
  OK             arms accruing, no absorbing exclusion, cells filling.

THE ONE THING THIS FENCE MAY NEVER DO is report OK because it found nothing to look at. An empty
tape, an absent design and a disabled epsilon are all LOUDER than a healthy desk, not quieter.

    python scripts/check_excitation.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block -- a governance fault must never
# silence the fence that reports on the desk's only execution experiment.
from libs.execution import excitation  # noqa: E402
from libs.ops.input_provenance import UNREADABLE, Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

# Days a denylisted symbol may sit blocked before the absence of a re-entry condition is a
# defect rather than a recent decision. L1.16a gives the alpha graveyard this discipline; this
# is the same clock pointed at the execution graveyard.
REENTRY_GRACE_DAYS = 30.0

#: WHERE A PRE-REGISTERED EXECUTION EXCITATION DESIGN FOR THE MT5 ORDER PATH WOULD LIVE. It does
#: not exist yet, and that absence is the finding rather than a missing-file complaint: the
#: gateway prices nine execution policies and five child algorithms on every pass and sends a
#: hard-coded order shape regardless, so the desk has no identifying variation in the treatment
#: its own cost model is fitted on. Beside the executor's other state, so it travels with the box.
MT5_DESIGN = "desks/mt5/data/execution_excitation_design.json"

#: The MT5 order tape: one row per order the gateway asked the venue for, written by
#: `gateway._record_intent` (gateway.py:971). This is the execution experiment's dataset -- it
#: carries the order type actually sent, the router's ranked advice, and the sleeve that asked.
MT5_INTENTS = "desks/mt5/data/order_intents.jsonl"

#: THE MT5 EXECUTION DENYLIST -- every artifact that stops the gateway opening new risk, and where
#: the way back for each is recorded. `required` follows L1.55: a file whose ABSENCE is itself a
#: meaningful measurement is not required; one whose absence would make the fence guess is.
#:   live_sleeve_policy.json   principal's roster admission; enforced at decision_core.load_sleeves
#:                             and FAILS CLOSED to XAUUSD-only defaults, so ABSENT still blocks.
#:   banned_families.json      family-level ban with a measured cause.
#:   GOLD_RETIRED.json         windows the promoter has retired; fails OPEN (absent = none).
#:   RETIRED_CLOSE_QUEUE.json  names whose open positions are being closed out.
#:
#: (relative path, scope label, required). Read in this order; every one is DECLARED (L1.55) so an
#: unreadable input makes the fence say UNMEASURED rather than publish an empty denylist, which
#: would be a CLAIM about the gateway this run has no evidence for.
_DENYLIST: tuple[tuple[str, str, bool], ...] = (
    ("desks/mt5/data/live_sleeve_policy.json", "roster_admission", False),
    ("desks/mt5/data/banned_families.json", "family_ban", False),
    ("desks/mt5/data/GOLD_RETIRED.json", "gold_window_retirement", False),
    ("desks/mt5/data/RETIRED_CLOSE_QUEUE.json", "retired_close_queue", False),
)

#: WHERE A WAY BACK IS RECORDED, per scope. An exclusion with none is ABSORBING (L1.16a): the
#: block stops the fills, so the evidence that would lift it can never accrue.
_REENTRY_SOURCES: tuple[tuple[str, str], ...] = (
    ("desks/mt5/data/GOLD_RETIRED_VOIDED.json", "gold_window_retirement"),
    ("desks/mt5/data/decay_actions.jsonl", "roster_admission"),
)


def _reentry_kind(entry: str, held_by: str, known: set[str]) -> str | None:
    """How this exclusion ends, or None when nothing records that it ever does.

    L1.16a ASKS FOR A RECORDED WAY BACK, NOT FOR A PARTICULAR KIND OF ONE, and the distinction
    matters on this desk because the two kinds live in different files:

      MECHANICAL  a predicate the desk re-evaluates on its own clock. `GOLD_RETIRED_VOIDED.json`
                  is the promoter re-deriving every standing gold retirement each pass and voiding
                  one it would refuse today; `decay_actions.jsonl` writes an explicit `reentry`
                  string on every retirement it makes. Both end the block with no human act.
      HELD        a named owner who can lift it, plus a recorded procedure. The principal's
                  `live_sleeve_policy.json` and `banned_families.json` are of this kind: each
                  carries who set it, why, and how it is removed.

    A HELD BLOCK IS NOT ABSORBING AND MUST NEVER BE REPORTED AS ONE. The absorbing defect is a
    block whose own existence destroys the evidence that would lift it, with nobody holding the
    key -- not a standing order with a named holder. Treating a principal's policy as a defect
    would have this fence pressing every hour to widen a roster the principal deliberately
    narrowed, which is a fence arguing with its own desk, and that is how a gate gets switched
    off. What stays a defect is an exclusion with NEITHER a predicate NOR an owner.
    """
    if any(entry == k or entry.startswith(k) or k.startswith(entry) for k in known if k):
        return "mechanical"
    if held_by.strip():
        return f"held:{held_by.strip()[:80]}"
    return None


def _blocked(root: Path, inp: Inputs, reentry: dict[str, set[str]]) -> list[dict[str, Any]]:
    """What the MT5 gateway currently refuses NEW RISK to, and whether each has a way back.

    Read from the same artifacts the gateway reads, so the fence and the gate can never disagree
    about who is blocked -- a fence reading a different file would be measuring a different desk.

    THAT PROMISE WAS UNENFORCEABLE UNTIL 2026-08-12 (R0396) and the shape of the failure carries
    across venues: the read was `except (OSError, JSONDecodeError): return []`, so an unreadable
    input made this function say NOBODY IS BLOCKED while the executor went on blocking -- a
    fail-OPEN on the L1.45 execution fence. An empty denylist and an unmeasurable one were
    byte-identical to every caller and only one of them is evidence. Every read below is DECLARED.
    """
    out: list[dict[str, Any]] = []
    malformed = 0
    for rel, scope, required in _DENYLIST:
        data = inp.read_json(root / rel, default=None, required=required)
        # A file that EXISTS and does not parse is promoted to required: a producer ran and wrote
        # garbage, and what it holds may be an exclusion this fence would otherwise report as
        # absent. ABSENT and UNREADABLE demand opposite responses and must never collapse (L1.55).
        if inp.records and inp.records[-1].status == UNREADABLE:
            inp.records[-1].required = True
        if not isinstance(data, dict):
            if scope == "roster_admission":
                # ABSENCE IS NOT PERMISSION HERE, and the fence must say so. The enforcer
                # (desks/mt5/mt5desk/live_policy.py) FAILS CLOSED: with no override file it
                # applies its own hard-coded defaults and goes on refusing. A fence that read the
                # missing file as "nothing is blocked" would disagree with the gate about who is
                # blocked, in the fail-open direction, which is the failure `_blocked` promises
                # cannot happen. The defaults are not copied here -- duplicating them is how the
                # two drift -- the enforcer is NAMED so the reader goes to the one definition.
                out.append({
                    "scope": scope, "entry": "<live_policy defaults>", "source": rel,
                    "why": "override file absent; desks/mt5/mt5desk/live_policy.py fails closed "
                           "to its hard-coded DEFAULT_LIVE_SYMBOLS / DEFAULT_BANNED_* and keeps "
                           "refusing -- read the enforcer for the exact set",
                    "reentry_kind": "held:principal (live_policy.py: widened only on the "
                                    "principal's word or on evidence the principal has accepted)",
                    "reentry_recorded": True})
            continue
        # (entry, why, held_by) -- `held_by` is the OWNER a document names as able to lift the
        # block, or "" when it names none. See `_reentry_kind`.
        entries: list[tuple[str, str, str]] = []
        try:
            if scope == "roster_admission":
                by = str(data.get("by") or "")
                live = data.get("live_symbols")
                if isinstance(live, list) and live:
                    entries.append(("every symbol outside " + ",".join(str(s) for s in live),
                                    str(data.get("rule") or "roster admission"), by))
                banned_tf = data.get("banned_timeframes")
                if isinstance(banned_tf, dict):
                    entries += [(f"{sym} {tf}", "banned timeframe", by)
                                for sym, tfs in banned_tf.items()
                                for tf in (tfs if isinstance(tfs, list) else [])]
                fams = data.get("banned_families")
                entries += [(f"family:{f}", "banned family", by)
                            for f in (fams if isinstance(fams, list) else [])]
            elif scope == "family_ban":
                banned = data.get("banned")
                # The file's `note` is the LIFT PROCEDURE ("a ban is lifted by removing its entry
                # here, on purpose, with the reason recorded in the desk lessons"); a per-family
                # `by` names who set it. Either is a recorded way back.
                lift = str(data.get("note") or "")
                entries += [(f"family:{k}", str((v or {}).get("why") or "unattributed"),
                             str((v or {}).get("by") or "") or lift)
                            for k, v in (banned or {}).items() if isinstance(banned, dict)]
            elif scope == "gold_window_retirement":
                entries += [(str(k), str((v or {}).get("reason") or "unattributed"), "")
                            for k, v in data.items()
                            if not k.startswith("_") and isinstance(v, dict)]
            elif scope == "retired_close_queue":
                entries += [(str(n), "retired; open positions being closed", "")
                            for n in (data.get("names") or [])
                            if isinstance(data.get("names"), list)]
        except (AttributeError, TypeError, ValueError):
            # L1.60: a skip is fine, an INVISIBLE skip is not -- a row this loop could not parse
            # is an exclusion whose status is unknown, and dropping it silently reads exactly like
            # an exclusion that does not exist.
            malformed += 1
            continue
        known = reentry.get(scope, set())
        for entry, why, held_by in entries:
            kind = _reentry_kind(entry, held_by, known)
            out.append({"scope": scope, "entry": entry, "why": why[:240], "source": rel,
                        "reentry_kind": kind, "reentry_recorded": kind is not None})
    if malformed:
        inp.defaulted("mt5 execution denylist",
                      detail=f"{malformed} source(s) unparseable -- their block status is unknown")
    return out


def _reentry_state(root: Path, inp: Inputs) -> dict[str, set[str]]:
    """Which blocked entries have a RECORDED way back, by scope.

    Absent file is NOT an error and NOT OK: it means no exclusion of that scope has ever been
    given a way back, which is exactly the ABSORBING finding this fence reports -- so it is
    declared NOT required and an empty set is a genuine measurement of "nothing has a way back".

    UNREADABLE is the opposite case and is promoted to required (R0396): a file that exists but
    does not parse means a producer ran and wrote garbage, and the entries inside it may each hold
    a re-entry condition this fence would then wrongly report as absent -- ABSORBING on a name
    that is not, or silence on one that is (L1.55).
    """
    out: dict[str, set[str]] = {}
    for rel, scope in _REENTRY_SOURCES:
        path = root / rel
        if path.suffix == ".jsonl":
            # `decay_actions.jsonl` carries an explicit `reentry` string per retirement -- the one
            # denylist on this desk that writes a machine-readable way back on every entry.
            try:
                lines = path.read_text("utf-8").splitlines()
            except OSError as exc:
                # NOT required: an absent ledger means no retirement of this scope has ever been
                # given a way back, which is a genuine measurement and the ABSORBING finding
                # itself -- never a reason to stop measuring.
                inp.defaulted(rel, detail=f"{exc!r} -- no recorded re-entry condition readable")
                continue
            names: set[str] = set()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and str(row.get("reentry") or "").strip():
                    names.add(str(row.get("sleeve") or ""))
            out.setdefault(scope, set()).update(n for n in names if n)
            continue
        data = inp.read_json(path, default=None, required=False)
        if inp.records and inp.records[-1].status == UNREADABLE:
            inp.records[-1].required = True
        if isinstance(data, dict):
            out.setdefault(scope, set()).update(
                str(k) for k, v in data.items()
                if not k.startswith("_") and isinstance(v, dict) and v.get("voided_why"))
    return out


def _tape(root: Path) -> list[dict[str, Any]]:
    """The MT5 order tape: one row per order the gateway asked the venue for.

    An unreadable tape yields nothing and the caller reports UNIDENTIFIED on zero rows, never OK:
    "we could not read the order history" and "the book has not traded" are different facts, and
    the second is the only one that is ever benign.
    """
    rows: list[dict[str, Any]] = []
    try:
        lines = (root / MT5_INTENTS).read_text("utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _variation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Is the order shape the gateway SENDS a deterministic function of the sleeve that asked?

    THIS IS THE WHOLE LAW, MEASURED FROM THE DESK'S OWN TAPE AND NOTHING ELSE. L1.45 says a
    controller that never perturbs cannot identify the cost surface it gates on. On the crypto
    desk the proof was that `maker_wait` was a deterministic function of side, so wait and side
    were perfectly collinear and no regression on own fills could separate them. Here the same
    question is asked of the MT5 tape: if every order a sleeve ever sent used one order type, then
    order type is collinear with sleeve BY CONSTRUCTION and the fitted shortfall cells are
    confounded however many fills accrue. No quantity of observational orders fixes that.

    A ROW WITH NO `order_type` IS COUNTED SEPARATELY AND NEVER AS A VALUE. Older intents predate
    that field, and folding their absence in as a distinct value made three sleeves look like
    they had VARIED their order type when what actually varied was the schema -- absence read as
    a measurement, which is the thing L1.28a exists to stop. Only rows that RECORD a type are
    eligible to demonstrate variation.

    THE ROUTER HALF IS COMPARED WITHOUT A MAPPING, deliberately. The executor ranks nine policies
    on every pass and writes the winner onto the intent; translating a policy name into an MT5
    order type would need a table this fence would then be asserting rather than reading. The
    mapping-free statement is stronger anyway: if the router's ranked winner takes several values
    while the order type actually sent takes one, the competition produced variation in its own
    ranking that never reached the venue.
    """
    by_sleeve: dict[str, set[str]] = {}
    router_choices: set[str] = set()
    priced = 0
    missing_type = 0
    for r in rows:
        sleeve = str(r.get("sleeve") or "<unnamed>")
        otype = r.get("order_type")
        if isinstance(otype, str) and otype:
            by_sleeve.setdefault(sleeve, set()).add(otype)
        else:
            missing_type += 1
        advice = r.get("policy_advice")
        if isinstance(advice, dict) and advice.get("policy"):
            priced += 1
            router_choices.add(str(advice["policy"]))
    varying = sorted(s for s, t in by_sleeve.items() if len(t) > 1)
    sent = sorted({t for ts in by_sleeve.values() for t in ts})
    return {
        "n_rows": len(rows),
        "n_rows_recording_order_type": len(rows) - missing_type,
        "n_rows_missing_order_type": missing_type,
        "n_sleeves_with_a_recorded_type": len(by_sleeve),
        "sleeves_with_varying_order_type": varying,
        "order_types_sent": sent,
        "n_priced_by_router": priced,
        "router_choices_ranked_first": sorted(router_choices),
        # THE ONE-LINE VERDICT the detail string is built from, so the claim published can never
        # be stronger than the rows behind it.
        "collinear": bool(by_sleeve) and not varying,
        "router_ranking_never_reached_the_venue": len(router_choices) > len(sent) >= 1,
    }


#: The gateway call that would make a design load-bearing. If this string is gone, arms are
#: assigned by nobody and the design is decorative however healthy the artifact looks.
_WIRING_MARKER = "excitation.assign("


def _executor_wired(root: Path) -> bool | None:
    """Is the MT5 gateway actually calling the design? None when the source cannot be read.

    WHY A FENCE READS SOURCE. 'No stamped fills' has two completely different causes with
    opposite fixes: the executor is not wired (go wire it), or it is wired and the book has not
    traded since (go accrue fills -- there is nothing to fix). Reporting the first when the
    second is true sends the next session to re-do work that is already done, which is exactly
    the failure this run hit once already on the TCA epoch. The tape alone cannot tell them
    apart, because both look like zero rows.

    POINTED AT THE LIVE ORDER PATH, 2026-09-23. It used to read
    `scripts/run_cashcarry_executor.py`, deleted with the crypto desk on 2026-09-05, so it
    returned None on every run -- and None means "there is no executor to measure", which had
    quietly become the permanent answer to a question nobody re-asked while a different executor
    traded every ten minutes.
    """
    try:
        return _WIRING_MARKER in (root / "desks/mt5/mt5desk/gateway.py").read_text("utf-8")
    except OSError:
        return None


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Pure: read design + tape + forensics, return the verdict. No writes -- tests call it."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)

    design = excitation.load_design(root / MT5_DESIGN)
    tape = _tape(root)

    # Tape rows that carry the excitation stamp at all -- i.e. were placed by an executor that
    # knows about arms. Rows predating the wiring are silent, not baseline: counting them as
    # controls would fabricate a control group out of history.
    stamped = [r for r in tape if r.get("exc_arm") is not None]
    randomised = [r for r in stamped if r.get("exc_baseline") is False]
    opens = [r for r in tape if r.get("ticket")]
    variation = _variation(tape)

    wired = _executor_wired(root)
    # THE DENYLIST IS A DECLARED READ (R0396, L1.55). `denylist_inp` covers exactly the artifacts
    # that answer "who is blocked"; if any is unmeasurable the fence must say so rather than
    # publish an empty list, because an empty denylist is a CLAIM about the executor.
    denylist_inp = Inputs("check_excitation._blocked")
    reentry = _reentry_state(root, denylist_inp)
    blocked = _blocked(root, denylist_inp, reentry)
    denylist_measured = denylist_inp.measured()
    absorbing = [b for b in blocked if not b["reentry_recorded"]] if denylist_measured else []

    unidentified = design.unidentified_cells
    # The MT5 tape carries no notional per row, so a spend against the declared cap is not
    # measurable until a design exists to declare one. UNMEASURED, published as such.
    spent = 0.0

    # STATUS -- worst first, and every empty-input case ranks ABOVE OK (L1.28a).
    if not design.loaded:
        status = "NO-DATA"
        # THE MEASURED STATE RIDES WITH THE MISSING FILE, so this reads as a finding about the
        # executor rather than a complaint about an artifact. Without a pre-registered design the
        # gateway has never varied its own order shape, and the tape says so in its own numbers.
        detail = (
            f"excitation design unusable: {design.note}. MEASURED on the order tape: "
            f"{variation['n_rows_recording_order_type']} of {len(tape)} intent(s) record an "
            f"order type, values {variation['order_types_sent'] or ['<none recorded>']}; "
            f"{len(variation['sleeves_with_varying_order_type'])} of "
            f"{variation['n_sleeves_with_a_recorded_type']} sleeve(s) ever sent more than one"
            + (" -- so order type is a DETERMINISTIC function of the sleeve, the two are "
               "perfectly collinear, and no quantity of observational fills can separate them"
               if variation["collinear"] else
               " -- some variation exists but none of it was assigned by a pre-registered design, "
               "so it cannot be read as an experiment")
            + (f". The router ranked {variation['n_priced_by_router']} of them first across "
               f"{len(variation['router_choices_ranked_first'])} different policies "
               f"({', '.join(variation['router_choices_ranked_first'])}) while "
               f"{len(variation['order_types_sent'])} order type(s) ever reached the venue -- the "
               "competition is measured and decides nothing"
               if variation["router_ranking_never_reached_the_venue"] else ""))
    elif design.epsilon <= 0.0 or design.daily_notional_cap_usd <= 0.0:
        status = "NO-EXCITATION"
        detail = (f"epsilon={design.epsilon}, cap=${design.daily_notional_cap_usd:.0f} -- "
                  f"excitation is switched off; a declared budget that is never spent is an "
                  f"idleness defect (L1.28a), not prudence")
    elif not denylist_measured:
        # BEFORE the ABSORBING slot, because this is the same question asked one level down:
        # ABSORBING says "these symbols are blocked with no way back", and an unmeasurable
        # denylist means the fence cannot say WHO is blocked at all. Falling through to
        # UNIDENTIFIED/OK would have been the fail-open the docstring forbids.
        status = "UNMEASURED"
        detail = (f"the execution denylist could not be read, so the fence cannot say who the "
                  f"executor is blocking -- {denylist_inp.why()}. An empty denylist is a CLAIM "
                  f"about the executor and this run has no evidence for it (L1.55/L1.28a)")
    elif absorbing:
        status = "ABSORBING"
        detail = (f"{len(absorbing)} execution exclusion(s) with NO recorded re-entry condition: "
                  f"{', '.join(b['entry'] for b in absorbing[:6])} -- the block stops the fills, "
                  f"so the evidence that would lift it can never accrue (L1.16a)")
    elif not stamped:
        status = "UNIDENTIFIED"
        detail = (
            f"0 of {len(tape)} tape rows carry an excitation stamp and the executor does NOT "
            f"call the design ({_WIRING_MARKER!r} absent) -- arms are assigned by nobody"
            if wired is False else
            f"executor source is UNREADABLE, so wiring cannot be confirmed; 0 of {len(tape)} "
            f"tape rows carry a stamp"
            if wired is None else
            f"executor IS wired, but 0 of {len(tape)} tape rows carry a stamp -- no open has "
            f"filled since the wiring landed. Nothing to fix: the design needs FILLS")
    elif not randomised:
        status = "UNIDENTIFIED"
        detail = (f"{len(stamped)} stamped fills but ZERO randomised arms -- every order took "
                  f"the baseline path, so the wait coefficient stays confounded with side")
    elif unidentified:
        status = "UNIDENTIFIED"
        detail = (f"{len(unidentified)} design cell(s) still at n_observed=0: "
                  f"{', '.join(unidentified)} -- these report UNIDENTIFIED, never a prior")
    else:
        status = "OK"
        detail = (f"{len(randomised)} randomised arms across {len(design.real_cells)} cells; "
                  f"${spent:.0f}/{design.daily_notional_cap_usd:.0f} of today's budget spent")

    return {
        "generated": now.isoformat(),
        "law": ("L1.45 -- a controller that never perturbs cannot identify the cost surface it "
                "gates on; exploration is mandatory in EXECUTION, not only in research"),
        "status": status,
        "detail": detail,
        "design_loaded": design.loaded,
        "executor_wired": wired,
        "epsilon": design.epsilon,
        "daily_notional_cap_usd": design.daily_notional_cap_usd,
        "arms": design.arms,
        "n_tape_rows": len(tape),
        "n_opens": len(opens),
        "n_stamped": len(stamped),
        "n_randomised": len(randomised),
        # NOT MEASURABLE FROM THE MT5 TAPE: an intent row carries lot, not notional, and there is
        # no declared cap to spend against until a design exists. None means unmeasured, and a
        # zero here would read as "the budget went unspent", which is a different claim (L1.28a).
        "spent_today_usd": None,
        "unidentified_cells": unidentified,
        "order_variation": variation,
        # THE REFUSAL PATH (R0396). `None` means "not measured"; `[]` means "measured, and nobody
        # is blocked". Those were the same value until 2026-08-12 and only one of them is
        # evidence -- a reader that cannot tell them apart audits the wrong organ.
        "execution_denylist": denylist_inp.derived(blocked),
        "absorbing_exclusions": denylist_inp.derived(absorbing),
        "denylist_provenance": denylist_inp.block(),
        "denylist_status": denylist_inp.status(),
        "reentry_recorded": {k: sorted(v)[:12] for k, v in sorted(reentry.items())},
        "next_action": (
            f"Pre-register an execution excitation design at {MT5_DESIGN} (arms/epsilon/cap) for "
            "the MT5 order path, then wire libs/execution/excitation.assign() into "
            "desks/mt5/mt5desk/gateway.py and persist Arm.as_tape_fields() onto every intent. An "
            "arm here varies HOW an order is placed -- the execution policy the router already "
            "ranks -- never HOW MUCH: no arm may touch lot, risk_frac, heat or any rail, so this "
            "adds identifying variation without changing the size of a single bet"
            if status == "NO-DATA" else
            "Raise epsilon above 0 -- the budget exists to be spent (L1.28a)"
            if status == "NO-EXCITATION" else
            f"Repair the denylist inputs before trusting any exclusion verdict: "
            f"{denylist_inp.why()}"
            if status == "UNMEASURED" else
            "Record a re-entry condition per blocked entry, the way decay_actions.jsonl already "
            "does for every retirement it writes: m minimum-size probes after d days (L1.16a)"
            if status == "ABSORBING" else
            ("Wire libs/execution/excitation.assign() into the gateway's order path and "
             "persist Arm.as_tape_fields() onto every intent" if wired is False else
             "ACCRUE FILLS -- the executor is wired and the design is loaded; the experiment is "
             "waiting on the book to trade, not on an engineering change")
            if status == "UNIDENTIFIED" else
            "Fit the cost surface: scripts/run_cost_identification.py"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/excitation_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"excitation (L1.45): {rep['status']} -- {rep['detail']}")
        print(f"  tape {rep['n_tape_rows']} rows | stamped {rep['n_stamped']} | "
              f"randomised {rep['n_randomised']} | epsilon {rep['epsilon']}")
        var = rep["order_variation"]
        print(f"  order types sent {var['order_types_sent']} over "
              f"{var['n_sleeves_with_a_recorded_type']} sleeve(s), "
              f"{len(var['sleeves_with_varying_order_type'])} of which ever sent more than one "
              f"({var['n_rows_missing_order_type']} row(s) record none) | router ranked "
              f"{var['n_priced_by_router']} first across "
              f"{len(var['router_choices_ranked_first'])} policies")
        for b in rep["execution_denylist"] or []:
            print(f"  BLOCKED [{b['scope']}] {b['entry']} -- "
                  f"{b['reentry_kind'] or 'NO re-entry condition'}")
        for r in rep["denylist_provenance"]:
            if r["status"] != "READ":
                print(f"  INPUT {r['status']}: {r['path']} -- {r.get('detail', '')}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 2 if rep["status"] in ("NO-DATA", "NO-EXCITATION", "UNMEASURED", "ABSORBING",
                                  "UNIDENTIFIED") else 0


if __name__ == "__main__":
    sys.exit(main())
