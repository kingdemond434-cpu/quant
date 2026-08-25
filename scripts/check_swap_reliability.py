#!/usr/bin/env python3
"""SWAP RELIABILITY (R0595) -- a model upgrade is gauntleted on CAPABILITY and nothing has ever
measured what it did to the seat's COMPLETED-RUN RATE.

WHAT model_upgrade.py ALREADY DOES, AND IT IS CORRECT. Before adopting a candidate it runs four
probes against it -- A LIVE (a non-empty answer), B CAPACITY (names the last file of a real full
payload), C FORMAT (parseable finding rows), D HONESTY (says ABSENT about a file not in the
payload) -- each with the incumbent as a control arm. That is an evidence-gated adoption and this
organ does not touch it.

WHAT NOBODY MEASURED. All four probes are SINGLE DRAWS. Reliability is a RATE OVER RUNS, so they
cannot see it by construction: a candidate can answer one probe beautifully and then finish fewer
of its real runs. The literature R0458 carries says these are different quantities and that the
gap runs in the dangerous direction -- capability gains buy only small reliability gains, and up
to 19% of failures are meltdown-by-ambition, where a MORE capable model attempts more ambitious
work and completes LESS of it. So a seat can pass all four probes, be adopted correctly, and
quietly lower the finished-run rate the panel actually consumes. UNMEASURED counts as zero
(L1.28a), and this was unmeasured.

THE ROW THAT ASKED FOR THIS NAMED THE WRONG DENOMINATOR, AND CHECKING WAS CHEAPER THAN BEING
WRONG. R0595 says `build_audit_coverage.record_attempts` (95289be5) already counts every seat
call, so the before/after rate is computable from an artifact that exists. It is not. That tally
is keyed by MODEL ID WITH NO SEAT IDENTITY, stored as a per-DAY count rather than per-run,
truncated at 30 days, and on 2026-08-20 it held 12 attempts across 4 `:free` seats on 3 dates --
seats DISJOINT from the paid roster model_upgrade.py actually swaps. It cannot answer "this
seat's rate before vs after its swap" on any axis.

`data/external_panel_log.jsonl` can, and already does: one row per seat per run, carrying
`provider` (the SEAT), `model` (what that seat was running), `ts` (the run), and `response` XOR
`error`. Completed vs died is already encoded there and the history reaches back to 2026-07-11.

THIS ORGAN BLOCKS NO UPGRADE AND SIZES NOTHING. It reads history after the fact; it is not in the
adoption path, it moves no probe and no bar. Its whole effect is to make "this swap raised the
seat's finished-run rate" distinguishable from "nobody has ever looked", which were byte-identical
until now.

THREE REFUSALS, AND THEY ARE THE LOAD-BEARING PART:

    UNDERPOWERED     fewer than _MIN_RUNS runs on one side of the swap. Two runs against three is
                     not a rate, and publishing one would be a number a reader acts on.
    CONFOUNDED       the panel's SIZE changed across the window. On 2026-07-28 the roster
                     collapsed 13 -> 4 when credits ran out, so seats either side of that boundary
                     are being compared under a different payload budget and a different roster.
                     Reading that fall as caused by a model swap would blame the model for an
                     unpaid invoice.
    AMBIGUOUS-SEAT   two seats in one run share a `provider` name (the roster really does carry
                     two `ai` and two `openai` seats). Their rows cannot be told apart, so their
                     curves must not be merged into one.

    python scripts/check_swap_reliability.py [--report-only] [--window N]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.input_provenance import (  # noqa: E402
    ABSENT,
    READ,
    UNREADABLE,
    InputRecord,
    Inputs,
)
from libs.ops.lawful import guard as _law_guard  # noqa: E402

LOG = _ROOT / "data/external_panel_log.jsonl"
OUT = _ROOT / "data/swap_reliability.json"

#: Runs required on EACH side of a swap before a rate is published. Deliberately in RUNS, not days
#: (L1.48): a busy month and a quiet one carry different evidence and the same calendar.
_MIN_RUNS: int = 4

#: How much the panel's seat count may move across a window before the comparison is CONFOUNDED.
#: The 2026-07-28 collapse was 13 -> 4, a factor of 3.25; anything at this scale is a change of
#: roster and budget rather than of one seat's model.
_SIZE_RATIO: float = 1.5

#: A completed-run rate must fall by at least this much to be called a regression rather than
#: noise. Not a bar anything has to clear -- nothing is promoted or blocked on it; it is the
#: threshold for printing the word REGRESSED next to a pair of measured rates.
_REGRESSION: float = 0.20

#: WHAT FAILS AND WHAT MERELY REPORTS, decided once and on the record. A MEASURED regression fails:
#: it is a finding with an action behind it (`model_upgrade.py --rollback` reverts exactly that
#: swap), and a found-unfixed defect is an unbooked loss (L1.28b). An unreadable log fails: the
#: panel is not recording and nothing downstream of it can be trusted. ALL-REFUSED does NOT fail --
#: it is a coverage gap whose repair is more runs and better seat names, and a fence that is red on
#: the day it is built gets switched off (L1.43), taking the regression detector with it.
_PASSING = ("OK", "NO-SWAPS-YET", "ALL-REFUSED")


def read_runs(path: Path, inputs: Inputs | None = None) -> tuple[list[dict[str, Any]], int]:
    """(runs oldest-first, rows that could not be parsed).

    THE ATTRITION COUNT IS NOT DECORATION (L1.60). A torn line is dropped -- correctly -- but a
    drop that leaves no trace makes "this run held no rows" and "this fence could not read them"
    byte-identical, and only one of those is a defect. Every unparseable line is counted and the
    count reaches the report.
    """
    rel = path.name
    try:
        text = path.read_text("utf-8")
    except FileNotFoundError:
        # ABSENT AND UNREADABLE STAY DISTINCT (L1.55): "the panel has never run" and "the panel
        # ran and wrote garbage" demand opposite repairs, and collapsing them sends a reader to
        # debug the wrong organ.
        if inputs is not None:
            inputs.records.append(InputRecord(rel, ABSENT, detail="no panel log has ever existed"))
        return [], 0
    except OSError as exc:
        if inputs is not None:
            inputs.records.append(InputRecord(rel, UNREADABLE, detail=repr(exc)))
        return [], 0
    if inputs is not None:
        inputs.records.append(InputRecord(rel, READ, detail=f"{len(text)} bytes"))

    by_ts: dict[str, list[dict[str, Any]]] = {}
    malformed = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(row, dict) or not row.get("ts") or not row.get("provider"):
            malformed += 1
            continue
        by_ts.setdefault(str(row["ts"]), []).append(row)
    runs = [{"ts": ts, "rows": rows} for ts, rows in sorted(by_ts.items())]
    return runs, malformed


def _completed(row: dict[str, Any]) -> bool:
    """A seat finished its run iff it returned a response. `error` and a bare row are both deaths.

    Read the same way run_external_panel.py records a loss (`"response" not in r`), so this organ
    and the panel's own telemetry can never disagree about what a completed run is.
    """
    return bool(str(row.get("response") or "").strip())


def seat_timeline(runs: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    """({seat: [{ts, model, completed}, ...]}, seats whose rows cannot be told apart).

    A seat that appears TWICE in one run is ambiguous by construction -- the roster carries two
    `ai` seats and two `openai` seats -- and merging two seats' curves under one name would
    manufacture a swap out of the alternation between them.
    """
    timeline: dict[str, list[dict[str, Any]]] = {}
    ambiguous: set[str] = set()
    for run in runs:
        seen = Counter(str(r.get("provider")) for r in run["rows"])
        for row in run["rows"]:
            seat = str(row.get("provider"))
            if seen[seat] > 1:
                ambiguous.add(seat)
            timeline.setdefault(seat, []).append({
                "ts": run["ts"], "model": str(row.get("model") or ""),
                "completed": _completed(row), "size": len(run["rows"])})
    return timeline, ambiguous


def swaps(timeline: dict[str, list[dict[str, Any]]], ambiguous: set[str], *,
          window: int = _MIN_RUNS) -> list[dict[str, Any]]:
    """Every observed seat swap, each graded MEASURED / UNDERPOWERED / CONFOUNDED / AMBIGUOUS-SEAT.

    A swap is a run in which a seat's model differs from what that same seat ran in the previous
    run it appeared in. The comparison takes the `window` runs either side -- the ones actually on
    the old and new model, never a fixed calendar slice.
    """
    out: list[dict[str, Any]] = []
    for seat, hist in sorted(timeline.items()):
        # AN AMBIGUOUS SEAT YIELDS ONE ROW, NOT ONE PER APPARENT SWAP, and that is a correctness
        # fix rather than tidying. When two seats share a name their rows alternate, so every run
        # looks like a model change: the first draft emitted FIFTEEN "swaps" for the `ai` seat,
        # none of which were swaps. Reporting an artifact fifteen times is how a detector gets
        # acked into silence (L1.37), and counting them would inflate n_swaps with non-events.
        if seat in ambiguous:
            models = sorted({h["model"] for h in hist if h["model"]})
            out.append({
                "seat": seat, "at": hist[0]["ts"], "from": "", "to": "",
                "n_before": 0, "n_after": 0, "verdict": "AMBIGUOUS-SEAT",
                "models_seen": models,
                "why": (f"two seats share the provider name {seat!r} within a single run, so "
                        f"their rows cannot be told apart and the {len(models)} model(s) seen "
                        "here are not one seat's history. Give the seats distinct names in "
                        "data/secrets/llm_panel.json and this becomes measurable.")})
            continue
        for i in range(1, len(hist)):
            before_model, after_model = hist[i - 1]["model"], hist[i]["model"]
            if not before_model or not after_model or before_model == after_model:
                continue
            pre = [h for h in hist[:i] if h["model"] == before_model][-window:]
            post = [h for h in hist[i:] if h["model"] == after_model][:window]
            rec: dict[str, Any] = {
                "seat": seat, "at": hist[i]["ts"], "from": before_model, "to": after_model,
                "n_before": len(pre), "n_after": len(post),
            }
            if len(pre) < window or len(post) < window:
                rec["verdict"] = "UNDERPOWERED"
                rec["why"] = (f"{len(pre)} run(s) before and {len(post)} after; {window} are "
                              "needed on each side before a rate means anything")
                out.append(rec)
                continue
            size_pre = sum(h["size"] for h in pre) / len(pre)
            size_post = sum(h["size"] for h in post) / len(post)
            lo, hi = sorted((size_pre, size_post))
            if lo <= 0 or hi / lo > _SIZE_RATIO:
                rec["verdict"] = "CONFOUNDED"
                rec["why"] = (f"the panel averaged {size_pre:.1f} seats before this swap and "
                              f"{size_post:.1f} after -- a roster and payload-budget change, so a "
                              "rate difference here is not attributable to the model")
                out.append(rec)
                continue
            r_pre = sum(h["completed"] for h in pre) / len(pre)
            r_post = sum(h["completed"] for h in post) / len(post)
            rec |= {"rate_before": round(r_pre, 3), "rate_after": round(r_post, 3),
                    "delta": round(r_post - r_pre, 3),
                    "verdict": "REGRESSED" if r_pre - r_post >= _REGRESSION else "MEASURED"}
            if rec["verdict"] == "REGRESSED":
                rec["why"] = (f"{seat} finished {r_pre:.0%} of its runs on {before_model} and "
                              f"{r_post:.0%} on {after_model}. The capability gauntlet cannot see "
                              "this: it draws once, and this is a rate.")
            out.append(rec)
    return out


def report(path: Path = LOG, *, window: int = _MIN_RUNS) -> dict[str, Any]:
    """The verdict over every swap the panel log can see."""
    inputs = Inputs(caller="check_swap_reliability.report")
    runs, malformed = read_runs(path, inputs)
    timeline, ambiguous = seat_timeline(runs)
    found = swaps(timeline, ambiguous, window=window)
    tally = dict(Counter(s["verdict"] for s in found))
    regressed = [s for s in found if s["verdict"] == "REGRESSED"]

    if not runs:
        status, nxt = "UNMEASURED", (
            f"{path} holds no readable panel runs, so no swap can be graded. This is NOT 'no "
            "swap hurt a seat' -- nobody looked (L1.28a). Check the panel is running at all.")
    elif not found:
        status, nxt = "NO-SWAPS-YET", (
            f"{len(runs)} run(s) across {len(timeline)} seat(s) and no model change among them. "
            "model_upgrade.py has never applied a panel swap (its `promoted` state is empty and "
            "the only `apply` in its log is the brain chain), so an empty result here is the "
            "correct measurement of an upgrade path that has not fired.")
    # OK IS UNREACHABLE WITHOUT A MEASURED SWAP, AND THE FIRST DRAFT GOT THIS WRONG ON REAL DATA.
    # It printed "OK -- no reliability regression" over 38 swaps of which ZERO were gradeable:
    # every one refused as underpowered, confounded or ambiguous. The exit code was 0 because the
    # run had examined 38 things, and the verdict was earned over none of them -- the L1.57
    # vacuous pass, inside the organ whose own docstring cites it. A verdict about swaps needs a
    # denominator of SWAPS.
    elif not tally.get("MEASURED") and not regressed:
        status, nxt = "ALL-REFUSED", (
            f"{len(found)} swap(s) seen and NONE gradeable: "
            + ", ".join(f"{v.lower()} {n}" for v, n in sorted(tally.items()))
            + ". This is a coverage gap, not a clean bill -- it says the desk cannot yet tell "
            "whether its swaps cost reliability. The gap is the work queue (L1.0): distinct seat "
            "names remove AMBIGUOUS-SEAT today, and every further panel run shrinks UNDERPOWERED.")
    elif regressed:
        worst = min(regressed, key=lambda s: s["delta"])
        status, nxt = "REGRESSED", (
            f"{len(regressed)} swap(s) lowered a seat's finished-run rate; worst is "
            f"{worst['seat']} {worst['rate_before']:.0%} -> {worst['rate_after']:.0%} on "
            f"{worst['at'][:10]}. Compare against the incumbent before keeping it: "
            "`python scripts/model_upgrade.py --rollback` reverts exactly this swap. Capability "
            "was measured at adoption and is not in question -- reliability was not.")
    else:
        status, nxt = "OK", (
            f"{tally.get('MEASURED', 0)} swap(s) measured with no reliability regression; "
            f"{len(found) - tally.get('MEASURED', 0)} refused as underpowered, confounded or "
            "ambiguous. A refusal is a real answer and is not a pass.")

    return {"status": status, "n_runs": len(runs), "n_seats": len(timeline),
            "n_swaps": len(found), "malformed_rows": malformed,
            "ambiguous_seats": sorted(ambiguous), "window": window,
            "tally": tally, "swaps": found,
            # L1.55: the inputs are declared beside the numbers, and `measured` says whether the
            # numbers rest on a read or on a default. An honest gap is CORRECT here; the failing
            # state is a declared-absent input still presented as a measurement.
            "provenance": inputs.block(), "measured": inputs.measured(), "why": inputs.why(),
            "next_action": nxt}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description="post-swap reliability, measured over real runs")
    ap.add_argument("--log", default=str(LOG), help="panel log to read")
    ap.add_argument("--window", type=int, default=_MIN_RUNS,
                    help="runs compared on each side of a swap")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = report(Path(args.log), window=args.window)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    except OSError as exc:
        print(f"  could not write {OUT}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"swap reliability: {rep['status']} -- {rep['n_swaps']} swap(s) over "
              f"{rep['n_runs']} run(s), {rep['n_seats']} seat(s)")
        for s in rep["swaps"]:
            rates = ("" if "rate_before" not in s
                     else f"  {s['rate_before']:.0%} -> {s['rate_after']:.0%}")
            print(f"  [{s['verdict']:<14}] {s['seat']:<24} {s['from']} -> {s['to']}{rates}")
            if s.get("why"):
                print(f"                   {s['why'][:110]}")
        if rep["malformed_rows"]:
            print(f"  {rep['malformed_rows']} unparseable log row(s) -- counted, not hidden")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # The denominator is the SWAPS graded, not the runs read (L1.57): a verdict about swaps earned
    # over zero swaps is vacuous, and NO-SWAPS-YET is the honest name for it rather than OK.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_runs"], of="panel runs",
                      fence="check_swap_reliability.py")


if __name__ == "__main__":
    sys.exit(main())
