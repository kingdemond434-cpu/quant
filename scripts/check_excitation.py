#!/usr/bin/env python3
"""EXCITATION FENCE (L1.45) -- the desk explores in research and must explore in EXECUTION too.

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
from libs.execution import excitation, execution_tape  # noqa: E402
from libs.ops.input_provenance import UNREADABLE, Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

# Days a denylisted symbol may sit blocked before the absence of a re-entry condition is a
# defect rather than a recent decision. L1.16a gives the alpha graveyard this discipline; this
# is the same clock pointed at the execution graveyard.
REENTRY_GRACE_DAYS = 30.0


def _bleeding_symbols(root: Path, inp: Inputs, reentry: dict[str, Any]) -> list[dict[str, Any]]:
    """Symbols the executor's `_structurally_bleeding` currently blocks from NEW OPENS.

    Read from the same artifact the executor reads, so the fence and the gate can never disagree
    about who is blocked -- a fence reading a different file would be measuring a different desk.

    THAT PROMISE WAS UNENFORCEABLE UNTIL 2026-08-12 (R0396). The read was
    `except (OSError, JSONDecodeError): return []`, so an unreadable forensics file made this
    function say NOBODY IS BLOCKED while the executor went on blocking -- the exact disagreement
    the docstring above forbids, in the fail-OPEN direction, on the L1.45 execution fence. An
    empty denylist and an unmeasurable one were byte-identical to every caller, and only one of
    them is evidence. The read is now DECLARED (L1.55): the caller gets `None` for "cannot know"
    and a list for "measured", and `build_report` refuses to publish a denylist it did not read.
    """
    # SAME KEY PRECEDENCE AS THE EXECUTOR (2026-08-13). `_structurally_bleeding` reads
    # `bleeding_symbols` -- the ALL-TIME verdict -- and falls through to the 14d-rolling
    # `worst_symbols` only when the all-time list is absent or empty. This read must mirror that
    # `or` exactly: reading `worst_symbols` alone would have this fence publish 2 blocked symbols
    # while the gate enforced 7, which is precisely the "fence and gate disagree about who is
    # blocked" failure the docstring above promises cannot happen (L1.61 -- the same claim
    # measured two ways from two sources is a contradiction nothing else on the desk can see).
    data = inp.read_json(root / "web/trade_forensics.json", default=None, required=True)
    rows = None
    if isinstance(data, dict):
        rows = data.get("bleeding_symbols") or data.get("worst_symbols")
    if not isinstance(rows, list):
        rows = []
    out = []
    seen: set[str] = set()
    malformed = 0
    for r in rows:
        try:
            if int(r.get("n", 0)) >= 5 and float(r.get("bps", 0.0)) <= -20.0:
                out.append({"symbol": str(r.get("symbol")), "n": int(r.get("n", 0)),
                            "bps": float(r.get("bps", 0.0))})
                seen.add(str(r.get("symbol")))
        except (AttributeError, TypeError, ValueError):
            # L1.60: a skip is fine, an INVISIBLE skip is not -- a row this loop could not parse
            # is a symbol whose block status is unknown, and dropping it silently reads exactly
            # like a symbol that is not blocked.
            malformed += 1
            continue
    if malformed:
        inp.defaulted("web/trade_forensics.json#worst_symbols",
                      detail=f"{malformed} row(s) unparseable -- their block status is unknown")
    # PERSISTENT HALF OF THE SAME DENYLIST (2026-08-05). `worst_symbols` is a 14-day ROLLING
    # window, so it empties while the book is paused and this fence would report ZERO exclusions
    # while the executor was still denying -- the exact "fence and gate disagree about who is
    # blocked" failure this function's docstring promises cannot happen. It could, because the
    # executor now also denies on a recorded re-entry row (see `_structurally_bleeding`), which
    # outlives the window. Read both, so the fence keeps measuring the desk it audits.
    for symbol, row in reentry.items():
        if symbol.startswith("_") or not isinstance(row, dict) or symbol in seen:
            continue
        verdict = row.get("original_verdict")
        verdict = verdict if isinstance(verdict, dict) else {}
        out.append({"symbol": symbol, "n": int(verdict.get("n", 0) or 0),
                    "bps": float(verdict.get("bps", 0.0) or 0.0)})
    return out


#: The executor call that makes the design load-bearing. If this string is gone, arms are assigned
#: by nobody and the design is decorative however healthy the artifact looks.
_WIRING_MARKER = "arm = _excitation_arm(sym, spot_side, qty)"


def _executor_wired(root: Path) -> bool | None:
    """Is the executor actually calling the design? None when the source cannot be read.

    WHY A FENCE READS SOURCE. 'No stamped fills' has two completely different causes with
    opposite fixes: the executor is not wired (go wire it), or it is wired and the book has not
    traded since (go accrue fills -- there is nothing to fix). Reporting the first when the
    second is true sends the next session to re-do work that is already done, which is exactly
    the failure this run hit once already on the TCA epoch. The tape alone cannot tell them
    apart, because both look like zero rows.
    """
    try:
        return _WIRING_MARKER in (root / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    except OSError:
        return None


def _reentry_state(root: Path, inp: Inputs) -> dict[str, Any]:
    """Recorded re-entry conditions for execution-denylisted symbols.

    Absent file is NOT an error and NOT OK: it means no exclusion has ever been given a way back,
    which is exactly the ABSORBING finding this fence reports -- so it is declared NOT required
    and an empty dict is a genuine measurement of "nothing has a way back".

    UNREADABLE is the opposite case and is promoted to required (R0396): a file that exists but
    does not parse means a producer ran and wrote garbage, and the symbols inside it may each
    hold a re-entry condition this fence would then wrongly report as absent -- ABSORBING on a
    symbol that is not, or silence on one that is. ABSENT and UNREADABLE demand opposite
    responses and the idiom this replaces collapsed them (L1.55).
    """
    data = inp.read_json(root / "data/execution_reentry.json", default=None, required=False)
    if inp.records and inp.records[-1].status == UNREADABLE:
        inp.records[-1].required = True
    return data if isinstance(data, dict) else {}


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Pure: read design + tape + forensics, return the verdict. No writes -- tests call it."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)

    design = excitation.load_design(root / "data/excitation_design.json")
    tape = execution_tape.read(path=root / "data/moat/execution_tape/cashcarry_trades.jsonl")

    # Tape rows that carry the excitation stamp at all -- i.e. were placed by an executor that
    # knows about arms. Rows predating the wiring are silent, not baseline: counting them as
    # controls would fabricate a control group out of history.
    stamped = [r for r in tape if r.get("exc_arm") is not None]
    randomised = [r for r in stamped if r.get("exc_baseline") is False]
    opens = [r for r in tape if r.get("event") == "open"]

    wired = _executor_wired(root)
    # THE DENYLIST IS A DECLARED READ (R0396, L1.55). `denylist_inp` covers exactly the two files
    # that answer "who is blocked"; if either is unmeasurable the fence must say so rather than
    # publish an empty list, because an empty denylist is a CLAIM about the executor.
    denylist_inp = Inputs("check_excitation._bleeding_symbols")
    reentry = _reentry_state(root, denylist_inp)
    bleeding = _bleeding_symbols(root, denylist_inp, reentry)
    denylist_measured = denylist_inp.measured()
    absorbing = [b for b in bleeding if b["symbol"] not in reentry] if denylist_measured else []

    unidentified = design.unidentified_cells
    spent = excitation.spent_today(tape, now=now)

    # STATUS -- worst first, and every empty-input case ranks ABOVE OK (L1.28a).
    if not design.loaded:
        status = "NO-DATA"
        detail = f"excitation design unusable: {design.note}"
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
        detail = (f"{len(absorbing)} execution exclusion(s) with NO re-entry condition: "
                  f"{', '.join(b['symbol'] for b in absorbing)} -- each blocked on n>=5, and "
                  f"because the block stops new opens, n can never grow past 5 (L1.16a)")
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
        "spent_today_usd": round(spent, 2),
        "unidentified_cells": unidentified,
        # THE REFUSAL PATH (R0396). `None` means "not measured"; `[]` means "measured, and nobody
        # is blocked". Those were the same value until 2026-08-12 and only one of them is
        # evidence -- a reader that cannot tell them apart audits the wrong organ.
        "execution_denylist": denylist_inp.derived(bleeding),
        "absorbing_exclusions": denylist_inp.derived(absorbing),
        "denylist_provenance": denylist_inp.block(),
        "denylist_status": denylist_inp.status(),
        "reentry_recorded": sorted(reentry),
        "next_action": (
            "Write data/excitation_design.json (pre-registered arms/epsilon/cap)"
            if status == "NO-DATA" else
            "Raise epsilon above 0 -- the budget exists to be spent (L1.28a)"
            if status == "NO-EXCITATION" else
            f"Repair the denylist inputs before trusting any exclusion verdict: "
            f"{denylist_inp.why()}"
            if status == "UNMEASURED" else
            "Record a re-entry condition per blocked symbol in data/execution_reentry.json: "
            "m minimum-size probes after d days (L1.16a)"
            if status == "ABSORBING" else
            ("Wire libs/execution/excitation.assign() into the executor's open path and "
             "persist Arm.as_tape_fields() onto every fill" if wired is False else
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
        for b in rep["absorbing_exclusions"] or []:
            print(f"  ABSORBING: {b['symbol']} n={b['n']} bps={b['bps']} -- no re-entry condition")
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
