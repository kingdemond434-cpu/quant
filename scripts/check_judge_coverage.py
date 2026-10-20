#!/usr/bin/env python3
"""THE JUDGE-COVERAGE FENCE -- every mined family is judged every hour, and the backlog falls.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth"
                                                                  -- the principal, 2026-09-23

WHAT THIS ASSERTS, against `desks/mt5/reports/JUDGE_COVERAGE.json`, which
`research/judge_coverage.py` writes at intake every hour:

  * NO FAMILY IS STARVED.  A family holding unjudged cells and absent from the hour's queue is a
    FAILURE. This is the defect that was measured: the judge re-tested a handful of families
    while `cross_asset_residual` (55,190 mined), `overnight_drift` (26,721) and
    `clock_transition` (20,081) waited. Absence from the queue is not low priority, it is never.
  * THE CARRIED BACKLOG FALLS, PER FAMILY.  Rows already in a family's backlog at the previous
    reading and STILL unjudged now are the carried cohort. A cell leaves it exactly one way -- by
    being judged -- so it can only fall, and a family whose carried count did not fall while it
    held backlog and held quota was starved in fact if not in the queue.
  * THE REMAINDER FOLLOWS THE PUBLISHED RANKING.  The floor is the breadth mandate and is
    covered by the starvation check; the remainder is where the return is, and it is spent
    strictly down expected value per judge-second. A family given remainder while a HIGHER-ranked
    family still held undrained backlog means the allocation stopped following its own ranking --
    which is exactly how a future session would quietly revert this to round-robin with the
    report still claiming value ordering.
  * NO FAMILY'S OLDEST UNJUDGED CELL EXCEEDS ITS OWN WINDOW.  A family's window is the hours its
    own quota needs to drain its own backlog, floored at the hour. A family of 55,190 cells is
    not failed for being large and a family of nine is not excused for being small.

WHY THE RATCHET IS ON THE CARRIED COHORT AND NOT ON RAW BACKLOG. Raw backlog rises whenever the
miners outrun the judge -- which is mining working, and mining is unrestricted by the principal's
standing order. A fence on the raw number would fail the desk for mining faster, would be
unsatisfiable in the direction it was pointed, and would be switched off inside a week; the
coverage-drain fence learned that lesson on a wall clock and it is written down there. The
carried cohort is the part intake actually controls: it is the promise that what the desk already
knew it had mined does not sit unjudged forever.

WHAT THIS FENCE NEVER DOES. It removes no cell, caps no book, shrinks no budget and slows no
miner (GROWTH_GOVERNANCE Rule 1). Its only remedy is ORDER -- and order costs nothing, because
the same rows reach the same judge under the same budget either way.

UNMEASURED IS A VERDICT (L1.28a). On a clean checkout there is no report and no ratchet; this
says UNMEASURED and exits 0, because "this machine has no desk state" is not "a law was broken".
On the box `--require-state` promotes an absent report to a FAILURE -- an organ that was
scheduled and produced nothing is exactly the defect L1.49 names. A pass in which the judge
recorded NO verdicts at all is UNMEASURED for the drain checks rather than a failure: nothing
drained because nothing ran, and that is the gauntlet's clock to answer for, not intake's.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: A sweep-to-sweep wobble in the pre-warm failure share below this is noise, not a regression.
PREWARM_TOLERANCE = 0.02
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "JUDGE_COVERAGE.json"
RATCHET = DESK / "data" / "judge_backlog_ratchet.json"
AUDIT = DESK / "reports" / "judge_coverage_fence.json"

#: A report older than this is stale: the organ runs at intake, hourly, so three hours of silence
#: means the clock stopped. Generous because a box reboot or a long sweep is not a law breach.
STALE_H = 6.0

#: How far past its OWN window a family's oldest unjudged cell may sit before this fails. The
#: slack exists because a window is derived from a quota measured on the previous hour's capacity
#: and the judge's capacity varies with the box; 2x is "this family is not being served", not
#: "this hour ran a little short".
WINDOW_SLACK = 2.0

#: A family with mined cells, not ONE real verdict ever (judged_total 0), and an oldest unjudged
#: cell older than this FAILS on the box (2026-10-14). Mirrors
#: `research/judge_coverage.NEVER_JUDGED_MAX_AGE_H`; a test pins the two together.
NEVER_JUDGED_MAX_AGE_H = 48.0

RULE = ("the judge rules on at least 150,000 cells a day; "
        "no family with mined cells goes unjudged past 48h; "
        "no family holding unjudged cells is absent from the hour's queue; each family's carried "
        "backlog falls; no family's oldest unjudged cell sits past twice its own drain window "
        "without moving; and the remainder after every floor follows the published "
        "expected-value-per-judge-second ranking")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


def _age_h(stamp: object, now: datetime) -> float | None:
    txt = str(stamp or "").strip()
    if not txt:
        return None
    try:
        at = datetime.fromisoformat(txt.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    return max(0.0, (now.timestamp() - at.timestamp()) / 3600.0)


def _armed(require_state: bool) -> bool:
    """Whether a state-derived verdict may FAIL here, by the law gate's host semantics.

    `--require-state` (the box's state battery) always arms it. Otherwise it is armed only on the
    trading host and never in a source view (`QUANT_LAWGATE_SOURCE_VIEW=1`, every laws-only run):
    the box publishes JUDGE_COVERAGE.json to origin every 15 minutes, so a clean CI or cloud
    checkout holds a COPY, and judging a copy as local runtime is the confusion 778815d6c removed
    from check_self_repair and check_birth_obligations. There the finding is published as WARN."""
    if require_state:
        return True
    if os.environ.get("QUANT_LAWGATE_SOURCE_VIEW") == "1":
        return False
    try:
        root = str(ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.ops import host_identity
        return bool(host_identity.identify().may_be_trading)
    except Exception:
        return False


def never_judged(fams: Mapping[str, Mapping[str, Any]], doc: Mapping[str, Any],
                 *, armed: bool) -> dict[str, Any]:
    """The never-judged check: mined > 0, judged_total == 0, oldest unjudged past 48 h.

    AN UNKNOWN AGE IS NOT A YOUNG ONE (L1.28a, audit of 4f28cd04). `judge_coverage` publishes
    `oldest_unjudged_age_h: None` when a family's backlog rows carry no `first_seen`; this check
    used to SKIP such a family, so mined > 0 with judged_total == 0 read OK -- "every family holds
    a real verdict" -- on exactly the rows the desk could not date. Such a family is now
    UNMEASURED and named; armed (the box's --require-state run, or the trading host) it FAILS with
    the aged ones, because a family that has never been judged and cannot even say for how long is
    not a family the fence may call fine."""
    published = doc.get("never_judged") if isinstance(doc.get("never_judged"), Mapping) else {}
    hits: list[tuple[str, float]] = []
    undated: list[str] = []
    for f, r in fams.items():
        if str(r.get("judging_status") or "") == "STUDY_ONLY":
            continue
        if int(r.get("mined") or 0) <= 0 or int(r.get("judged_total") or 0) != 0:
            continue
        age = r.get("oldest_unjudged_age_h")
        if age is None:
            # Nothing waiting (every cell parked or set aside) is not an undated wait.
            if int(r.get("unjudged", 1) or 0) > 0:
                undated.append(f)
            continue
        if float(age) <= NEVER_JUDGED_MAX_AGE_H:
            continue
        hits.append((f, float(age)))
    hits.sort(key=lambda fa: -fa[1])
    undated.sort(key=lambda f: -int(fams[f].get("mined") or 0))
    if not hits and not undated:
        return {"metric": "never_judged", "state": "OK", "families": [],
                "why": (f"every family with mined cells holds a real verdict, or its oldest cell "
                        f"is under {NEVER_JUDGED_MAX_AGE_H:.0f}h")}

    def _reason(f: str) -> str:
        row = published.get(f) if isinstance(published.get(f), Mapping) else None
        txt = (row or {}).get("reason") or fams[f].get("never_judged_reason")
        return str(txt) if txt else "no reason published"

    named = [{"family": f, "mined": int(fams[f].get("mined") or 0),
              "oldest_unjudged_age_h": a, "reason": _reason(f)} for f, a in hits]
    named += [{"family": f, "mined": int(fams[f].get("mined") or 0),
               "oldest_unjudged_age_h": None, "age": "UNMEASURED", "reason": _reason(f)}
              for f in undated]
    tail = ("" if armed else
            " -- published, not failed: this is a source view or a host that does not run the "
            "judge; the box's --require-state run fails it")
    parts: list[str] = []
    if hits:
        head = "; ".join(f"{n['family']} (mined {n['mined']}, oldest "
                         f"{n['oldest_unjudged_age_h']:.0f}h: {n['reason'][:160]})"
                         for n in named[:4] if n["oldest_unjudged_age_h"] is not None)
        parts.append(f"{len(hits)} family(ies) have mined cells and NEVER a real verdict, oldest "
                     f"past {NEVER_JUDGED_MAX_AGE_H:.0f}h: {head}")
    if undated:
        parts.append(f"{len(undated)} family(ies) have mined cells, NEVER a real verdict and NO "
                     f"datable backlog row (oldest_unjudged_age_h is None: rows lack first_seen), "
                     f"so their wait is UNMEASURED, not short: "
                     + ", ".join(f"{f} (mined {int(fams[f].get('mined') or 0)})"
                                 for f in undated[:6]))
    state = "FAIL" if armed else ("WARN" if hits else "UNMEASURED")
    return {"metric": "never_judged", "state": state, "families": named,
            "undated": undated, "why": "; ".join(parts) + tail}


#: The judging rate the principal set (2026-10-14: "100-200k cells a day"). Mirrors
#: `research/judge_coverage.JUDGING_RATE_TARGET_PER_DAY`; a test pins the two together.
JUDGING_RATE_TARGET_PER_DAY = 150_000


def judging_rate(doc: Mapping[str, Any], *, require_state: bool, armed: bool) -> dict[str, Any]:
    """Verdicts per day against the floor, from the report's `judging_rate` block.

    Below target: FAIL when armed (the box's --require-state run or the trading host), WARN in a
    source view -- the never-judged check's host semantics. An absent block, an UNMEASURED one,
    or a PARTIAL one whose lower bound is still short is UNMEASURED: FAIL under --require-state
    (a rate the box cannot state is the defect L1.49 names), UNMEASURED otherwise.
    """
    raw = doc.get("judging_rate")
    jr: Mapping[str, Any] | None = raw if isinstance(raw, Mapping) else None
    try:
        target = int((jr or {}).get("target_per_day") or JUDGING_RATE_TARGET_PER_DAY)
    except (TypeError, ValueError, OverflowError):        # Infinity / NaN -> the floor
        target = JUDGING_RATE_TARGET_PER_DAY
    target = max(target, JUDGING_RATE_TARGET_PER_DAY)       # the floor only ratchets up (L1.50)
    got_raw = (jr or {}).get("verdicts_24h")
    status = str((jr or {}).get("status") or "")
    # A NON-FINITE RATE IS UNMEASURED, never a crash (audit of 0bf4ce83e: Infinity raised
    # OverflowError here) and never a pass: only a finite count is a reading.
    got: int | None = (int(got_raw) if isinstance(got_raw, (int, float))
                       and not isinstance(got_raw, bool) and math.isfinite(got_raw) else None)
    measured = got is not None and status in ("MEASURED", "PARTIAL")
    if got is not None and measured and got >= target:
        return {"metric": "judging_rate", "state": "OK", "verdicts_24h": got, "target": target,
                "why": f"{got} verdicts in 24h, at or above the {target}/day floor"}
    if got is None or not measured or status == "PARTIAL":
        why = ("JUDGE_COVERAGE carries no judging_rate block" if jr is None else
               f"judging rate {status or 'UNMEASURED'}: "
               f"{(jr or {}).get('why') or 'no verdict count'}")
        return {"metric": "judging_rate", "state": "FAIL" if require_state else "UNMEASURED",
                "verdicts_24h": got, "target": target,
                "why": why + (" -- --require-state says this box owes the rate (L1.49)"
                              if require_state else "")}
    short = target - got
    return {"metric": "judging_rate", "state": "FAIL" if armed else "WARN",
            "verdicts_24h": got, "target": target, "shortfall_per_day": short,
            "why": (f"{got} verdicts in 24h against the {target}/day floor "
                    f"({got / target:.1%}; short {short}/day): add judge capacity -- "
                    "never throttle a miner, never move a gate"
                    + ("" if armed else
                       " -- published, not failed: this is a source view or a host that does "
                       "not run the judge; the box's --require-state run fails it"))}


#: Mirrors research/judge_coverage.TAPE_CERT_MIN_JUDGED (the test pins them equal): tape families
#: judged past this many cells with the tape deep enough and 0 certificates fail. At a 1% per-cell
#: pass rate P(0 of 500) = 0.66%.
TAPE_CERT_MIN_JUDGED = 500


def tape_produces(doc: Mapping[str, Any], *, armed: bool,
                  require_state: bool) -> dict[str, Any]:
    """THE TICK TAPE MUST PRODUCE CERTIFICATES (principal 2026-10-14 07:25Z). Once the tape holds
    the need (60 development days + lockbox on at least one symbol), it FAILS armed / WARNs in a
    source view when (a) a tape family has mined > 0 and NO named verdict in 24 h, or (b) tape
    families together judged > TAPE_CERT_MIN_JUDGED cells and hold 0 certificates. Absent tape
    state is UNMEASURED, never a zero; a report with no tape block at all fails --require-state
    (the box owes it, L1.49)."""
    tape = doc.get("tape")
    if not isinstance(tape, Mapping):
        return {"metric": "tape_produces", "state": "FAIL" if require_state else "UNMEASURED",
                "why": "JUDGE_COVERAGE carries no tape block"
                       + (" -- --require-state says this box owes it (L1.49)" if require_state
                          else "")}
    depth = tape.get("depth") if isinstance(tape.get("depth"), Mapping) else {}
    fams = tape.get("families") if isinstance(tape.get("families"), Mapping) else {}
    if tape.get("status") != "MEASURED" or depth.get("status") != "MEASURED":
        return {"metric": "tape_produces", "state": "UNMEASURED",
                "why": f"tape state UNMEASURED: {tape.get('why') or depth.get('why')}"}
    need = depth.get("days_needed")
    if not depth.get("meets_need", int(depth.get("symbols_at_need") or 0) > 0):
        return {"metric": "tape_produces", "state": "OK",
                "why": (f"the tape does not yet hold the need ({depth.get('max_days')} trading "
                        f"days on the deepest symbol vs {need}; ETA "
                        f"{depth.get('eta_days_to_judgeable')}d -- {depth.get('eta_rule')}): "
                        "nothing judgeable is owed yet")}
    silent = sorted(f for f, r in fams.items() if isinstance(r, Mapping)
                    and int(r.get("mined") or 0) > 0
                    and int(r.get("named_verdicts_24h") or 0) == 0)
    judged = sum(int(r.get("judged_total") or 0) for r in fams.values()
                 if isinstance(r, Mapping))
    certs = tape.get("certificates_total")
    barren = certs is not None and int(certs) == 0 and judged > TAPE_CERT_MIN_JUDGED
    if not silent and not barren:
        return {"metric": "tape_produces", "state": "OK",
                "why": (f"tape at need ({depth.get('symbols_at_need')} symbol(s) >= {need} "
                        f"trading days); every mined tape family has a named verdict in 24h; "
                        f"certificates {certs} on {judged} judged")}
    parts = []
    if silent:
        parts.append("tape family(ies) with mined cells and NO named verdict in 24h while the "
                     "tape meets the need: " + ", ".join(
                         f"{f} (mined {int(fams[f].get('mined') or 0)}, shippable "
                         f"{int(fams[f].get('shippable') or 0)}, judged_total "
                         f"{int(fams[f].get('judged_total') or 0)})" for f in silent))
    if barren:
        parts.append(f"tape families judged {judged} cells (> {TAPE_CERT_MIN_JUDGED}) with the "
                     f"tape at need and hold 0 certificates")
    return {"metric": "tape_produces", "state": "FAIL" if armed else "WARN",
            "families": silent, "judged": judged, "certificates": certs,
            "why": "; ".join(parts) + ("" if armed else
                                       " -- published, not failed: source view / non-judge host")}


def judge(report: Path | None = None, *, require_state: bool = False,
          now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    path = report or REPORT
    doc = _read(path)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "rule": RULE,
                           "report": str(path), "checks": []}
    if not isinstance(doc, dict) or not doc.get("families"):
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        out["why"] = (f"{path.name} is absent or carries no family table"
                      + (" and --require-state says this box owes one (L1.49)" if require_state
                         else "; this tree holds no judge-coverage state (L1.28a)"))
        return out

    age = _age_h(doc.get("at"), at)
    if age is not None and age > STALE_H:
        out["checks"].append({"metric": "freshness", "state": "FAIL" if require_state else "WARN",
                              "why": f"report is {age:.1f}h old, past the {STALE_H:.0f}h lease"})

    fams: dict[str, Any] = {f: r for f, r in (doc.get("families") or {}).items()
                            if isinstance(r, dict)}
    judged_any = sum(int(r.get("judged_window") or 0) for r in fams.values())
    failures: list[str] = []

    # 0. NEVER JUDGED (2026-10-14). A floor quota on a family the judge never rules on is a quota
    #    nobody consumed: orderflow_imbalance and liquidity_regime sat at judged_total 0 for 782h
    #    and 499h while every check below read OK. Age alone is the trigger here, deliberately --
    #    a family with NO verdict has no movement to ratchet, and two days without one is not a
    #    short hour. Armed by the same host semantics as the law gate's other state checks.
    nj = never_judged(fams, doc, armed=_armed(require_state))
    out["checks"].append(nj)
    if nj["state"] == "FAIL":
        failures.extend(n["family"] for n in nj["families"][:10])
    # 0b. THE TICK TAPE PRODUCES CERTIFICATES (principal 2026-10-14), see `tape_produces`.
    tp = tape_produces(doc, armed=_armed(require_state), require_state=require_state)
    out["checks"].append(tp)
    if tp["state"] == "FAIL":
        failures.extend([f"tape:{f}" for f in tp.get("families") or []] or ["tape_produces"])

    # 1. STARVATION: unjudged cells and no place in the queue.
    starved = sorted((f for f, r in fams.items()
                      if int(r.get("shippable", r.get("unjudged")) or 0) > 0
                      and int(r.get("queued") or 0) == 0
                      and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                     key=lambda f: -int(fams[f].get("unjudged") or 0))
    if starved:
        failures.extend(starved[:10])
        out["checks"].append({
            "metric": "families_starved", "state": "FAIL",
            "why": (f"{len(starved)} family(ies) hold unjudged cells and got no share of the "
                    f"hour: " + ", ".join(f"{f} ({fams[f].get('unjudged')})"
                                          for f in starved[:5]))})
    else:
        out["checks"].append({"metric": "families_starved", "state": "OK",
                              "why": "every family holding unjudged cells is in the queue"})

    # 2. THE CARRIED COHORT FALLS. UNMEASURED on the first reading (no baseline) and on a pass
    #    where the judge recorded nothing at all (nothing ran; that is not intake's failure).
    rows_with_baseline = [(f, r) for f, r in fams.items() if r.get("carried") is not None
                          and int(r.get("prior_unjudged") or 0) > 0]
    if not rows_with_baseline:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": "no previous reading to ratchet against"})
    elif judged_any == 0:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": ("the judge recorded no verdict in this window -- nothing "
                                      "drained because nothing ran (the gauntlet's clock)")})
    else:
        # Against the COHORT BASE when the report carries it: the prior backlog plus cells the
        # bank re-admitted, minus cells parked as not testable since (neither is judging).
        def _base(r: dict) -> int:
            b = r.get("cohort_base")
            return int(r.get("prior_unjudged") or 0) if b is None else int(b or 0)

        stalled = sorted((f for f, r in rows_with_baseline
                          if _base(r) > 0 and int(r.get("carried") or 0) >= _base(r)
                          and int(r.get("quota") or 0) > 0
                          and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                         key=lambda f: -int(fams[f].get("carried") or 0))
        if stalled:
            failures.extend(stalled[:10])
            out["checks"].append({
                "metric": "carried_backlog", "state": "FAIL",
                "why": (f"{len(stalled)} family(ies) drained nothing they already held: "
                        + ", ".join(f"{f} ({fams[f].get('carried')} carried of "
                                    f"{fams[f].get('prior_unjudged')})" for f in stalled[:5]))})
        else:
            drained = sum(int(r.get("drained") or 0) for _, r in rows_with_baseline)
            out["checks"].append({"metric": "carried_backlog", "state": "OK",
                                  "why": f"{drained} carried cell(s) left the backlog this pass"})

    # 3. NO FAMILY PAST ITS OWN WINDOW -- AND THE AGE IS RATCHETED ON MOVEMENT, NOT ON ITS VALUE.
    #
    # An age RISES by the wall time between two readings whatever the desk does. The coverage-
    # drain fence ratcheted a raw wait and went red on its third live pass for exactly that
    # reason -- 6.0h to 6.3h, eighteen minutes of clock -- and a gate nobody can satisfy is a gate
    # that gets switched off. So what fails here is an age that is past twice the family's own
    # drain window AND DID NOT FALL, in a pass where the family held quota and the judge actually
    # recorded verdicts. That is the controllable defect: a family whose stream is sorted
    # oldest-first, which was served this hour, and whose oldest cell still did not move.
    # The first reading carries no baseline and so enters UNMEASURED, which is how every metric
    # on this desk enters: at its measurement, never at an invented zero.
    def _overdue(f: str, r: dict[str, Any]) -> bool:
        if int(r.get("unjudged") or 0) <= 0 or str(r.get("judging_status") or "") == "STUDY_ONLY":
            return False
        age = r.get("oldest_unjudged_age_h")
        prior = r.get("prior_oldest_age_h")
        if age is None or prior is None or int(r.get("quota") or 0) <= 0 or judged_any == 0:
            return False
        window = float(r.get("window_h") or 1.0)
        return float(age) > WINDOW_SLACK * window and float(age) >= float(prior)

    overdue = sorted((f for f, r in fams.items() if _overdue(f, r)),
                     key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
    if overdue:
        failures.extend(overdue[:10])
        out["checks"].append({
            "metric": "oldest_unjudged", "state": "FAIL",
            "why": (f"{len(overdue)} family(ies) were served this hour and their oldest cell "
                    f"still did not move, past twice their own drain window: " + ", ".join(
                        f"{f} ({fams[f].get('oldest_unjudged_age_h')}h vs "
                        f"{fams[f].get('window_h')}h window)" for f in overdue[:5]))})
    else:
        stale_age = sorted((f for f, r in fams.items()
                            if r.get("oldest_unjudged_age_h") is not None
                            and int(r.get("unjudged") or 0) > 0
                            and float(r["oldest_unjudged_age_h"]) >
                            WINDOW_SLACK * float(r.get("window_h") or 1.0)),
                           key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
        out["checks"].append({
            "metric": "oldest_unjudged",
            "state": "OK" if not stale_age else "WARN",
            "why": ("no family's oldest unjudged cell is past its own window" if not stale_age
                    else (f"{len(stale_age)} family(ies) hold a cell past their own window and "
                          f"it is FALLING or unmeasured (oldest "
                          f"{fams[stale_age[0]].get('oldest_unjudged_age_h')}h on "
                          f"{stale_age[0]}) -- published, not failed: an age rises with the "
                          "clock and only its movement is the desk's to control"))})

    # 4. THE REMAINDER FOLLOWED THE PUBLISHED RANKING. The floor is the breadth mandate and is
    #    checked above by starvation; this checks the part that carries the return. Remainder is
    #    spent strictly down expected value per judge-second, so a family that received remainder
    #    while a HIGHER-ranked family still held undrained backlog means the allocation stopped
    #    following its own ranking -- which is exactly how a future session would quietly revert
    #    this to round-robin, with the report still claiming value ordering.
    ranking = [r for r in (doc.get("value_ranking") or ()) if isinstance(r, dict)]
    if not ranking:
        out["checks"].append({"metric": "remainder_follows_ranking", "state": "UNMEASURED",
                              "why": "the report publishes no value ranking"})
    else:
        starved_higher: list[str] = []
        for i, row in enumerate(ranking):
            if int(row.get("remainder") or 0) <= 0:
                continue
            for higher in ranking[:i]:
                # Room on what SHIPS: cells the bank holds out of the docket take no remainder.
                room = (int(higher.get("shippable", higher.get("unjudged")) or 0)
                        - int(higher.get("quota") or 0))
                if int(higher.get("remainder") or 0) == 0 and room > 0:
                    starved_higher.append(f"{row.get('family')} over {higher.get('family')}")
                    break
        if starved_higher:
            failures.extend(starved_higher[:10])
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "FAIL",
                "why": ("the remainder did not follow the published expected-value-per-judge-"
                        "second ranking: " + ", ".join(starved_higher[:5]))})
        else:
            top = ranking[0]
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "OK",
                "why": (f"remainder spent down the ranking, top {top.get('family')} at "
                        f"{top.get('ev_per_judge_second')} ev/judge-s")})

    # 5. THE UNKNOWN CLASS RATCHETS DOWN AND MAY NOT STALL (principal 2026-09-23). MEASURED on
    #    the box: 44,432 of 60,000 recent verdicts terminated with no named gate -- three
    #    quarters of the judge returning neither a pass nor a reason, the largest single waste on
    #    the desk. `judge_coverage.name_unknowns` gives every one of them a NAMED reason and
    #    `update_unrunnable_bank` filters the unrunnable ones out of intake, so the count must
    #    fall. It FAILS on a rise, and on a STALL while the bank still had cells to filter --
    #    a count that stops falling with work left is how this silently returns. A count already
    #    at zero stalls at zero and passes; the first reading has no baseline and is UNMEASURED.
    tot = doc.get("totals") or {}
    now_unknown = tot.get("unknown_total")
    was_unknown = tot.get("prior_unknown_share")
    unnamed = int(tot.get("unknown_unnamed") or 0)
    share_now = tot.get("unknown_share")
    if now_unknown is None or share_now is None:
        out["checks"].append({"metric": "unknown_ratchet", "state": "UNMEASURED",
                              "why": "no UNKNOWN census in this report"})
    elif unnamed > 0:
        failures.append("unknown_unnamed")
        out["checks"].append({
            "metric": "unknown_ratchet", "state": "FAIL",
            "why": (f"{unnamed} UNKNOWN verdict(s) carry no named reason -- an unnamed terminal "
                    "state is the defect, whatever the cause turns out to be")})
    elif was_unknown is None:
        out["checks"].append({
            "metric": "unknown_ratchet", "state": "UNMEASURED",
            "why": (f"UNKNOWN share enters at its measurement ({float(share_now):.1%}, "
                    f"{now_unknown} cells, all named); no previous reading to ratchet against")})
    else:
        parked = int(tot.get("unrunnable_bank") or 0)
        rose = float(share_now) > float(was_unknown) + 1e-9
        # A STALL IS ONLY A STALL IF THE JUDGE RAN. The share is read from the sealed judge's own
        # verdict file, which does not move between its sweeps -- so without this guard the fence
        # would go red for the crime of being asked twice in one hour, which is precisely how the
        # coverage-drain fence learned that an unsatisfiable gate gets switched off. A RISE still
        # fails unguarded: a share cannot rise without new verdicts arriving.
        has_stalled = (abs(float(share_now) - float(was_unknown)) <= 1e-9
                       and float(share_now) > 0 and parked > 0 and judged_any > 0)
        if rose or has_stalled:
            failures.append("unknown_share")
            out["checks"].append({
                "metric": "unknown_ratchet", "state": "FAIL",
                "why": (f"UNKNOWN share {'rose' if rose else 'stalled at'} "
                        f"{float(was_unknown):.1%} -> {float(share_now):.1%} with {parked} "
                        "cell(s) in the unrunnable bank: the filter is not reaching the judge")})
        else:
            out["checks"].append({
                "metric": "unknown_ratchet", "state": "OK",
                "why": (f"UNKNOWN share {float(was_unknown):.1%} -> {float(share_now):.1%}, "
                        f"{now_unknown} cells, every one named"
                        + ("" if judged_any else
                           " (unchanged because the judge recorded no verdict this window --"
                           " a stall is only a stall if the judge ran)"))})

    # 6. THE JUDGE KEEPS PACE WITH CREATION (principal 2026-09-30: "the cells thing always
    #    permanently fixed"). Measured that day: ~8,300 cells created a day against ~5,300
    #    verdicts, so 1.4M unjudged and growing ~3k a day while the old meter read "25 h to
    #    drain". The drain status is the backlog's own movement between two readings, net of
    #    judging and creation. Two consecutive GROWING readings FAIL. THE REMEDY IS CAPACITY,
    #    NEVER LESS MINING: `research/judging_throughput.py` raises workers and cadence off this
    #    same report, and the unrunnable bank keeps dead cells from eating the judge. A single
    #    GROWING reading WARNs, because one sweep's timing is not a trend.
    drain = tot.get("drain_status")
    prior_drain = tot.get("prior_drain_status")
    if drain is None:
        out["checks"].append({"metric": "judge_keeps_pace", "state": "UNMEASURED",
                              "why": "no drain status in this report"})
    elif drain == "GROWING" and prior_drain == "GROWING":
        failures.append("judge_keeps_pace")
        out["checks"].append({
            "metric": "judge_keeps_pace", "state": "FAIL",
            "why": (f"backlog grew across two readings ({tot.get('backlog_growth_per_hour')}/h; "
                    f"judge sustains {tot.get('capacity_sustained_per_hour')}/h): add judge "
                    "capacity -- never throttle a miner")})
    else:
        out["checks"].append({"metric": "judge_keeps_pace",
                              "state": "WARN" if drain == "GROWING" else "OK",
                              "why": f"drain {drain} (previous {prior_drain})"})

    # 7. BUILD/DATA FAILURES BEFORE JUDGING RATCHET DOWN. Measured 2026-09-30: 20,247 of 29,466
    #    pre-warm builds failed on build or data. Those cells are now parked with a named reason
    #    and re-admitted only when their bars appear or grow, so the share may not rise.
    pw_now, pw_was = tot.get("prewarm_fail_share"), tot.get("prior_prewarm_fail_share")
    if pw_now is None or pw_was is None:
        out["checks"].append({"metric": "prewarm_fail_ratchet", "state": "UNMEASURED",
                              "why": f"pre-warm failure share {pw_now} (previous {pw_was})"})
    elif float(pw_now) > float(pw_was) + PREWARM_TOLERANCE:
        failures.append("prewarm_fail_share")
        out["checks"].append({
            "metric": "prewarm_fail_ratchet", "state": "FAIL",
            "why": (f"pre-warm build/data failure share rose {float(pw_was):.1%} -> "
                    f"{float(pw_now):.1%}: failing cells are reaching the judge again")})
    else:
        out["checks"].append({"metric": "prewarm_fail_ratchet", "state": "OK",
                              "why": f"pre-warm failures {float(pw_was):.1%} -> "
                                     f"{float(pw_now):.1%}"})

    # 8. THE JUDGING RATE (principal 2026-10-14: "judges even 100-200k cells a day"). Verdicts in
    #    the last 24 h from the judge's own ledger against the 150,000/day floor.
    jr = judging_rate(doc, require_state=require_state, armed=_armed(require_state))
    out["checks"].append(jr)
    if jr["state"] == "FAIL":
        failures.append("judging_rate")

    totals = doc.get("totals") or {}
    out["totals"] = {k: totals.get(k) for k in (
        "families_mined", "families_with_backlog", "families_queued", "families_starved",
        "unjudged_total", "carried_total", "study_only_total", "capacity_measured",
        "oldest_unjudged_age_h", "value_at_risk", "value_deferred", "value_forgone_per_hour",
        "hours_to_drain", "capacity_short", "unknown_total", "unknown_share",
        "unknown_unnamed", "never_fires_cells", "unrunnable_parked", "unrunnable_bank",
        "drain_status", "backlog_growth_per_hour", "capacity_sustained_per_hour",
        "prewarm_fail_share", "not_run_named", "shippable_total", "parked_unrunnable_total",
        "families_never_judged", "verdicts_24h", "judging_rate_target_per_day")}
    out["unknown_reasons"] = (doc.get("unknown_reasons") or {}).get("by_reason") or {}
    out["top_value"] = [{k: r.get(k) for k in ("rank", "family", "ev_per_judge_second",
                                               "p_optimistic", "prior_status", "quota",
                                               "floor", "remainder", "value_at_risk")}
                        for r in ranking[:5]]
    out["worst_backlog"] = (doc.get("worst_backlog") or [])[:5]
    out["verdict"] = "FAIL" if failures else "PASS"
    out["why"] = (f"{len(set(failures))} family(ies) failed a coverage rule: "
                  + ", ".join(sorted(set(failures))[:6])) if failures else (
        "every family holding unjudged cells is queued, its carried backlog fell, and none sits "
        "past its own window")
    return out


def render(doc: Mapping[str, Any]) -> list[str]:
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}"]
    for row in doc.get("checks") or ():
        lines.append(f"  [{row.get('state')}] {row.get('metric')}: {row.get('why')}")
    t = doc.get("totals") or {}
    if t.get("unknown_total") is not None:
        lines.append(f"  UNKNOWN {t.get('unknown_total')} ({t.get('unknown_share')}) "
                     f"reasons {doc.get('unknown_reasons')} unnamed {t.get('unknown_unnamed')} "
                     f"bank {t.get('unrunnable_bank')}")
    if t.get("value_at_risk") is not None:
        lines.append(f"  value at risk {t.get('value_at_risk')} / deferred "
                     f"{t.get('value_deferred')} / forgone {t.get('value_forgone_per_hour')}/h"
                     + ("  CAPACITY SHORT -> judging_throughput" if t.get("capacity_short")
                        else ""))
    for row in doc.get("top_value") or ():
        lines.append(f"  #{row.get('rank')} {row.get('family')} ev/judge-s "
                     f"{row.get('ev_per_judge_second')} quota {row.get('quota')}")
    for row in doc.get("worst_backlog") or ():
        lines.append(f"  worst: {row.get('family')} unjudged {row.get('unjudged')} "
                     f"queued {row.get('queued')} oldest {row.get('oldest_unjudged_age_h')}h")
    return lines


#: R0237: the exit code is `fence_exit` over a DECLARED pass set, never "fail on one named status,
#: pass on everything else" -- that sent any unforeseen or misspelled status down `else 0`. The
#: set is exactly the statuses this fence already exited 0 on (behaviour unchanged for every
#: status it can emit); what changes is that a status nobody declared now fails closed.
_PASSING = frozenset({"PASS", "UNMEASURED"})


def _exit(status: object) -> int:
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.ops.fence_exit import fence_exit
    return fence_exit(status, _PASSING, fail=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--require-state", action="store_true",
                    help="box mode: an absent or stale report is a FAILURE, not UNMEASURED")
    ap.add_argument("--report", default=None)
    ap.add_argument("--audit", default=str(AUDIT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = judge(report=Path(args.report) if args.report else None,
                require_state=bool(args.require_state))
    if args.json:
        print(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    else:
        for line in render(doc):
            print(line)
    if args.audit:
        with suppress(OSError):
            _write(Path(args.audit), doc)
    return _exit(doc["verdict"])


__all__ = ["JUDGING_RATE_TARGET_PER_DAY", "NEVER_JUDGED_MAX_AGE_H", "RATCHET", "REPORT", "RULE",
           "STALE_H", "TAPE_CERT_MIN_JUDGED", "WINDOW_SLACK", "judge", "judging_rate", "main",
           "never_judged", "render", "tape_produces"]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
