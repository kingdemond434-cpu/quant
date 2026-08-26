"""The live-path guard: the ONE production caller for the S1 rails (gap register row 2).

Every mechanism this script drives was built, unit-tested green, and called by nobody -- the
stage machine most of all: before this file, `libs/execution/staging.py` was imported only by its
own test. That is the failure mode this desk keeps repeating, and on the live path it would mean
arriving at Gate 0 with rails that have never once executed outside pytest.

Each tick, in this order:
  1. §3  reconcile   -- every live position must carry a venue-side reduce-only stop; naked >60s
                        freezes new entries and pages.
  2. §4  ladder      -- unacknowledged pages escalate 15m/60m/4h; the top rung latches.
  3. §5  canary      -- 6h round-trip health; failure or excess latency degrades for 6h.
  4. §6  ramp gate   -- the authorized size fraction, from arithmetic only.
  5. stage machine   -- tripwires DEMOTE. Promotion is evaluated and REPORTED, never taken:
                        S1 entry needs `principal_signoff`, which is a human act, and nothing in
                        this file may ever set it.

SAFETY, by construction:
  - Fully inert at S0 / without keys. The venue is only read when binance_live reports armed, so
    on a box with no keyfile this script reads local state and writes a report.
  - It never places an order, never arms anything, never writes LIVE_ENABLE or the signoff flag.
  - Its only write into the trading path is the EXISTING data/CASHCARRY_KILL freeze file, which
    the executor already honours -- a new parallel halt mechanism would be one more thing that
    can disagree with the real one.
  - Flattening at ladder rungs 60m/4h is a live-money action, so it is gated on being armed AND
    on --allow-flatten, which the scheduled unit does not pass. Left to a human or to a
    deliberately configured unit; the default run reports what it WOULD do.

    python scripts/run_live_guard.py [--allow-flatten] [--rearm WHO]
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.execution import canary as canary_mod
from libs.execution import gate0_evidence, ramp_gate, staging
from libs.execution import protective_stops as stops
from libs.ops.derisk_ladder import LadderState, unacked_since
from libs.ops.input_provenance import Inputs

_ROOT = Path(__file__).resolve().parent.parent
_REPORT = _ROOT / "data" / "live_guard.json"
_ALERTS = _ROOT / "data" / ".last_alerts.json"
_ACK = _ROOT / "data" / "PAGE_ACK"
_KILL = _ROOT / "data" / "CASHCARRY_KILL"
_RAMP = _ROOT / "data" / "ramp_state.json"
#: The ramp's step-up conditions require an 8-week trailing window, so evidence older than a week
#: is describing a book the desk no longer has. Declared here rather than at the read so the
#: tolerance is a reviewable constant and not a magic number inside a call (L1.44).
_RAMP_MAX_AGE_H = 168.0
_PRINCIPAL = _ROOT / "data" / "PRINCIPAL_ACTION.md"

#: DECLARES THAT THIS DESK HAS NO FUTURES LEG, ON PURPOSE. Written by the principal and
#: never by an organ -- like every other file that changes what the rails believe.
#:
#: WHY IT HAD TO EXIST. Measured 2026-08-15. The principal is Irish retail, so EEA derivatives are
#: unavailable under MiCA and the futures account cannot be read at all. The futures KEYFILE still
#: existed, so `_venue()` returned the futures connector as armed, `positions()` raised, and
#: `_reconcile` did the correct thing for a carry desk: FAILED CLOSED, reporting `<unreadable>` as
#: a naked position and freezing the executor. Sixty seconds later it did it again.
#:
#: That is a rail firing accurately at a book that no longer exists. The §3 invariant is about
#: LEVERAGED positions whose stop must survive the host's death; a spot holding has no liquidation
#: price and no counterparty call, so the invariant does not apply to it -- but "does not apply"
#: must be STATED, because the alternative reading is that spot positions are covered and they are
#: not. The report says so on every tick rather than going quiet.
#:
#: The freeze it produced was correct in mechanism and wrong in premise, which is the hardest kind
#: to see: nothing was broken, and the book could not trade.
_SPOT_ONLY = _ROOT / "data" / "SPOT_ONLY"


def _spot_only() -> bool:
    return _SPOT_ONLY.exists()


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _ack_ts() -> float:
    """When the operator last acknowledged the pager. 0.0 = never (so everything is unacked)."""
    try:
        return _ACK.stat().st_mtime
    except OSError:
        return 0.0


def _venue() -> Any | None:
    """The live FUTURES connector, ONLY if it is fully armed. None otherwise -- and None must
    mean 'we cannot see the book', never 'the book is clean'.

    Under `data/SPOT_ONLY` this returns None DELIBERATELY, and the distinction is the whole point:
    `_reconcile` treats None as "no futures positions can exist" rather than as a failed read, and
    that is only true because the desk has declared it has no futures leg. Without the marker the
    same None would be a lie about an unreadable venue.
    """
    if _spot_only():
        return None
    try:
        from libs.execution import binance_live
    except ImportError:
        return None
    try:
        return binance_live if binance_live.is_armed()[0] else None
    except Exception:
        return None


def _arming() -> tuple[bool, bool, str | None]:
    """Arming state of BOTH legs. Returns (futures_armed, spot_armed, hazard).

    The deployed sleeve is cash-and-carry -- delta-neutral only while both legs can trade. Armed
    on futures but not spot is not "half ready", it is a directional book wearing a hedged
    book's risk limits: the perp leg opens and the spot leg that was supposed to cancel it
    cannot. That asymmetry is worth naming explicitly rather than leaving as two booleans nobody
    compares.
    """
    fut = spot = False
    try:
        from libs.execution import binance_live
        fut = bool(binance_live.is_armed()[0])
    except Exception:
        fut = False
    try:
        from libs.execution import binance_spot_live
        spot = bool(binance_spot_live.is_armed()[0])
    except Exception:
        spot = False
    hazard = None
    if _spot_only():
        # NOT HALF-ARMED, DELIBERATELY ONE-LEGGED. The hazard below describes a cash-and-carry
        # book that lost a leg. A desk that never had a futures leg is a different object, and
        # reporting it as a degraded carry book would demote the stage every tick forever while
        # naming a risk -- an unhedgeable perp position -- that cannot arise.
        return fut, spot, None
    if fut != spot:
        have, missing = ("futures", "spot") if fut else ("spot", "futures")
        hazard = (f"HALF-ARMED: {have} leg armed, {missing} leg is NOT -- a cash-and-carry book "
                  f"cannot stay delta-neutral on one leg")
    return fut, spot, hazard


def _freeze(on: bool, reason: str) -> str:
    """Drive the existing executor kill file. Idempotent."""
    if on:
        if not _KILL.exists():
            _KILL.write_text(f"live_guard freeze {datetime.now(tz=UTC).isoformat()}: {reason}\n",
                             "utf-8")
            return "freeze ENGAGED"
        return "freeze already engaged"
    # Never auto-lift: the file may have been placed by the dead-man, the operator, or another
    # rail, and this script cannot tell which. Lifting someone else's halt is how a book comes
    # back up into the condition that took it down.
    return "no freeze required (existing kill file, if any, left alone)"


def _reconcile(venue: Any, now: float) -> tuple[stops.ReconcileReport, str]:
    if venue is None:
        rep = stops.ReconcileReport(naked={}, breaches={}, n_positions=0)
        if _spot_only():
            # SAYING WHAT IS NOT COVERED, EVERY TICK. A clean §3 line next to a live spot book
            # reads as "the book is protected". It is not: §3 is about leveraged positions whose
            # stop must outlive the host, and a spot holding has neither a liquidation price nor a
            # venue-side stop here. Silence would be the more dangerous of the two reports.
            return rep, ("SPOT_ONLY -- no futures leg exists, so no leveraged position can. Spot "
                         "holdings are OUTSIDE the §3 invariant: they carry no venue-side stop "
                         "and none is claimed. Their risk is drawdown, not liquidation")
        return rep, "connector not armed -- venue not read (no positions can exist)"
    try:
        positions = venue.positions()
        orders = venue.open_orders()
    except Exception as e:
        # fail-closed: we could not verify the rail, so we behave as though it is broken.
        rep = stops.ReconcileReport(naked={"<unreadable>": 0.0},
                                    breaches={"<unreadable>": stops.NAKED_GRACE_S + 1},
                                    n_positions=-1)
        return rep, f"venue read FAILED ({e!r} ) -- treating as naked, fail-closed"
    return stops.reconcile(positions, orders, now), "venue read ok"


def _canary_venue(venue: Any) -> tuple[Any, str]:
    """WHAT THE PROBE SHOULD BE PROVING: that the venue WE TRADE still answers a signed call.

    On a spot-only desk `venue` is None by design, and the old code then skipped the probe
    forever -- so the canary's last recorded state stayed whatever it was when the futures leg was
    still being read, and `consecutive_failures` could never come back down. A health check that
    can only ever hold its last verdict is not a health check; it is a stuck gauge, and this one
    contributes a tripwire.

    The probe's value is unchanged by which leg it runs on: it catches revoked keys, IP-whitelist
    drift and recvWindow skew. Pointing it at the spot connector on a spot-only desk aims it at the
    credential that actually matters here.
    """
    if venue is not None:
        return venue, "futures"
    if not _spot_only():
        return None, "none"
    try:
        from libs.execution import binance_spot_live as spot
    except ImportError:
        return None, "none"
    try:
        return (spot, "spot") if spot.is_armed()[0] else (None, "none")
    except Exception:
        return None, "none"


def _canary(venue: Any, now: float) -> tuple[canary_mod.CanaryState, str]:
    st = canary_mod.CanaryState.load(_ROOT / "data" / "canary_state.json")
    if not st.is_due(now):
        return st, "not due"
    venue, leg = _canary_venue(venue)
    if leg == "spot" and venue is not None:
        t0 = time.time()
        try:
            venue.balances()
            st.record(ok=True, latency_ms=(time.time() - t0) * 1000.0, now=now,
                      detail="signed spot balances read")
            return st, "probe ok (spot leg)"
        except Exception as e:
            st.record(ok=False, latency_ms=(time.time() - t0) * 1000.0, now=now, detail=repr(e))
            return st, f"probe FAILED (spot leg): {e!r}"
    if venue is None:
        # Do NOT record an attempt: an unarmed desk has no execution path to prove, and logging
        # failures here would bury a real outage under thousands of S0 rows.
        return st, "due, but connector not armed -- skipped (no attempt recorded)"
    t0 = time.time()
    try:
        # READ-ONLY probe. The spec's round-trip places a minimum-notional order; that is a
        # live-money action and stays behind the same --allow-flatten class of human gate, so
        # the scheduled probe exercises auth + signing + clock skew via a signed read instead.
        # This catches revoked keys, IP-whitelist drift and recvWindow skew -- everything except
        # order-placement itself, which the first S1 trade proves.
        venue.account_summary()
        st.record(ok=True, latency_ms=(time.time() - t0) * 1000.0, now=now,
                  detail="signed account read")
        return st, "probe ok"
    except Exception as e:
        st.record(ok=False, latency_ms=(time.time() - t0) * 1000.0, now=now, detail=repr(e))
        return st, f"probe FAILED: {e!r}"


def _ramp(now: float) -> tuple[float, str, dict[str, bool], Inputs]:
    """The size ladder, AND the provenance of the evidence it was decided on (L1.55).

    `data/ramp_state.json` has never existed on this box -- `run_cost_identification.py` is its
    only producer and has never published. The old `_load(_RAMP, {})` returned its default for
    that absence exactly as for an empty file, so the floor constant `SIZE_STEPS[0]` and six
    never-evaluated conditions were published as a MEASUREMENT and consumed by the executor
    through a freshness contract that reported FRESH. The number is unchanged here -- absence
    must keep the ramp at its floor -- but the artifact now says WHICH of the two reasons it is
    at the floor, because "the evidence failed" and "there is no evidence" are different claims
    and only one of them is true (L1.51: a clamp carries a lifting condition).
    """
    inp = Inputs("run_live_guard._ramp")
    state = inp.read_json(_RAMP, default={}, max_age_h=_RAMP_MAX_AGE_H)
    if not isinstance(state, dict):
        inp.defaulted(str(_RAMP.name), "artifact is not a JSON object")
        state = {}
    current = float(state.get("size_fraction", ramp_gate.SIZE_STEPS[0]))
    evidence = state.get("evidence", {}) if isinstance(state.get("evidence"), dict) else {}
    nxt, why = ramp_gate.next_step(current, evidence)
    checks = ramp_gate.step_up_conditions(evidence)
    if nxt != current:
        state["size_fraction"] = nxt
        state.setdefault("history", []).append(
            {"ts": now, "from": current, "to": nxt, "why": why})
        state["history"] = state["history"][-200:]
        _RAMP.write_text(json.dumps(state, indent=2), "utf-8")
    return nxt, why, checks, inp


def _promo_evidence(inp: Inputs, *, root: Path, keys_present: bool,
                    connector_verified: bool, capital_fraction: float) -> dict[str, Any]:
    """The evidence dict `staging.s1_entry_met`/`s2_entry_met` is judged on.

    L1.61 FABRICATED-SIDE REPAIR (R0536/R0537). Two of the five S1 criteria used to be built from
    sources that DO NOT EXIST: consent was read from `data/stage_state.json['principal_signoff']`
    -- A KEY NO CODE ANYWHERE WRITES -- and `symbol_count` arrived only through the ramp_state
    evidence spread, a file that has never existed, so `int(...)` defaulted to 0. Both published
    False permanently while the Gate-0 board, calling this SAME gate function, measured both True
    from the real artifacts. Neither side could see it, because each read its own source
    successfully; that is exactly the contradiction no single-artifact instrument can detect.

    The repair is the INPUT, never the verdict, and it is ONE SHARED READER per criterion
    (libs/execution/gate0_evidence.py) so a future edit cannot re-diverge the two organs.

    IT OPENS NOTHING. `keys_present` is False on an unarmed box, so the gate stays shut on its own
    genuine grounds, and `effective_size_fraction` -- the only number the executor consumes from
    this artifact -- never reads either value. What changes is that two criteria stop being
    DEFAULTS rendered as measurements.

    Extracted from `main()` so the repair is testable without constructing a venue connector: the
    defect it closes was invisible precisely because nothing ever exercised this dict.
    """
    symbols = gate0_evidence.symbol_count(root)
    if symbols is None:
        # None is not zero. An unreadable config must not publish a count nobody measured -- leave
        # the key absent and let s1_entry_met's own fail-closed default refuse it.
        inp.defaulted(gate0_evidence.CONFIG_REL, "config unreadable -- symbol_count unmeasured")
    return {
        # The ramp spread still supplies the S2 criteria (live_weeks, calibration_rows,
        # critical_drill_failures, cost_ratio). Every key below it is explicit and wins.
        **((inp.read_json(root / "data" / "ramp_state.json", default={},
                          max_age_h=_RAMP_MAX_AGE_H) or {}).get("evidence", {}) or {}),
        "keys_present": keys_present,
        "connector_verified": connector_verified,
        "capital_fraction": capital_fraction,
        "principal_signoff": gate0_evidence.principal_signoff(root),
        **({} if symbols is None else {"symbol_count": symbols}),
    }


def main() -> int:
    now = time.time()
    allow_flatten = "--allow-flatten" in sys.argv
    venue = _venue()
    stage = staging.current_stage()

    if "--rearm" in sys.argv:
        who = sys.argv[sys.argv.index("--rearm") + 1] if len(sys.argv) > (
            sys.argv.index("--rearm") + 1) else "operator"
        lad = LadderState.load(_ROOT / "data" / "derisk_state.json")
        done = lad.rearm(who, now)
        lad.save()
        print(f"ladder re-arm by {who}: {'cleared' if done else 'nothing latched'}")
        return 0

    # 1. §3 no-naked-position invariant --------------------------------------------------
    rep, recon_note = _reconcile(venue, now)

    # 2. §4 pager de-risk ladder ---------------------------------------------------------
    lad = LadderState.load(_ROOT / "data" / "derisk_state.json")
    since = unacked_since(_load(_ALERTS, {}), _ack_ts(), lad.oldest_unacked_ts)
    lad.update(since, now)
    rung = lad.effective()
    lad.save()

    # 3. §5 canary -----------------------------------------------------------------------
    can, canary_note = _canary(venue, now)
    can.save()
    mode = can.mode(now)

    # 4. §6 ramp gate --------------------------------------------------------------------
    size_fraction, ramp_why, ramp_checks, ramp_inp = _ramp(now)

    # 5. stage machine: DEMOTE on tripwire, never self-promote ---------------------------
    fut_armed, spot_armed, half_armed = _arming()

    tripwires: list[str] = []
    if half_armed:
        tripwires.append(half_armed)
    if rep.freeze_entries:
        tripwires.append(f"naked position >{stops.NAKED_GRACE_S:.0f}s")
    if rung.requires_manual_rearm:
        tripwires.append("pager ladder at 4h rung (disarmed)")
    if can.consecutive_failures >= 2:
        tripwires.append(f"canary failed {can.consecutive_failures}x consecutively")

    demoted = None
    if tripwires and stage != "S0":
        ok, target = staging.demote("; ".join(tripwires))
        demoted = target if ok else None

    # promotion is EVALUATED and REPORTED only. principal_signoff is a human act; this script
    # reads the flag and never writes it, so a green gate here is a prompt for the principal,
    # not a transition.
    # THE SAME ABSENT FILE FEEDS THE PROMOTION GATE (L1.55). A green S1 gate writes a
    # principal-action file telling a human the preconditions for LIVE CAPITAL are met, so the
    # provenance of the evidence behind it is published beside the verdict and never assumed.
    promo_inp = Inputs("run_live_guard.promo_evidence")
    promo_evidence = _promo_evidence(
        promo_inp, root=_ROOT, keys_present=venue is not None,
        connector_verified=can.last_ok_ts is not None, capital_fraction=size_fraction)
    gate_met, gate_why = (staging.s1_entry_met(promo_evidence) if stage == "S0"
                          else staging.s2_entry_met(promo_evidence))

    # freeze the executor while the invariant is breached or the ladder disallows entries
    freeze_needed = rep.freeze_entries or not rung.entries_allowed
    freeze_note = _freeze(freeze_needed, "; ".join(tripwires) or "ladder entries disabled")

    # flattening is live money: gated on armed AND explicit human opt-in
    flatten_note = "not required"
    if rung.flatten:
        if venue is not None and allow_flatten:
            try:
                res = venue.flatten_all()
                flatten_note = f"FLATTENED {len(res)} position(s) at rung {rung.name}"
            except Exception as e:
                flatten_note = f"flatten FAILED at rung {rung.name}: {e!r}"
        else:
            flatten_note = (f"rung {rung.name} requires flatten -- NOT executed "
                            f"(armed={venue is not None}, --allow-flatten={allow_flatten})")

    # SCOPED AT THE COMPUTATION, not just in the report (2026-08-01). The canary attests the
    # LIVE path and is deliberately SKIPPED while the connector is unarmed, so it can never
    # clear at S0 -- a verdict whose own probe refuses to run must not size a PAPER book.
    # Scoping only the emitted JSON left this line still halving the book while the artifact
    # claimed 1.0: artifact and behaviour disagreeing is worse than the original bug.
    _canary_mult = mode.size_multiplier if venue is not None else 1.0
    effective_size = size_fraction * rung.size_multiplier * _canary_mult

    report = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "stage": stage,
        "armed": venue is not None,
        "arming": {"futures": fut_armed, "spot": spot_armed, "hazard": half_armed},
        "reconcile": {"naked": rep.naked, "breaches": {k: round(v, 1)
                                                       for k, v in rep.breaches.items()},
                      "n_positions": rep.n_positions, "freeze_entries": rep.freeze_entries,
                      "summary": rep.summary, "note": recon_note},
        "ladder": {"rung": rung.name, "entries_allowed": rung.entries_allowed,
                   "size_multiplier": rung.size_multiplier,
                   "requires_manual_rearm": rung.requires_manual_rearm,
                   "unacked_since": lad.oldest_unacked_ts},
        # SCOPED TO THE PATH IT PROVES (2026-08-01). The canary attests the LIVE venue path --
        # signed reads, key validity, clock skew, IP whitelisting. When the connector is unarmed
        # _canary() skips WITHOUT recording an attempt (by design: an unarmed desk has no
        # execution path to prove), so last_ok_ts stays None forever and mode() reads limit_only
        # forever. That verdict was reaching the PAPER book and suppressing its taker fallbacks
        # (run_cashcarry_executor:1128), so the desk could not accrue the very forward evidence
        # its own Gate-0 net_of_fees criterion demands -- observed as OPEN-FAIL on candidates the
        # entry gate had passed. Applying a live-path verdict to a paper book is a category error,
        # not caution. The moment the connector IS armed the probe runs for real and this binds
        # again unchanged; a canary that RUNS and FAILS still returns limit_only immediately.
        "canary": {"mode": ("limit_only" if (mode.limit_only and venue is not None) else "normal"),
                   # Scoped exactly as the mode is: a probe that attests the LIVE path and is
                   # deliberately skipped at S0 cannot justify halving a PAPER book. Leaving
                   # it at 0.5 held effective size at 0.05 (ramp 0.1 x canary 0.5), so the
                   # desk opened ~1 carry and accrued ~1 close/day -- too slow to reach a
                   # decidable sample. Binds in full the moment the connector arms.
                   "size_multiplier": (mode.size_multiplier if venue is not None else 1.0),
                   "reason": (mode.reason if venue is not None else
                              mode.reason + " -- NOT BINDING at S0: the probe attests the LIVE "
                              "path and is deliberately skipped while the connector is unarmed, "
                              "so it can never clear here. Binds in full the moment S1 arms."),
                   "consecutive_failures": can.consecutive_failures, "note": canary_note},
        # L1.55: the numbers AND where they came from. `checks` is None -- not six `false`
        # values -- when the evidence file is absent, because an unevaluated condition rendered
        # as a failed one is the fabrication this law exists to stop. check_idle_cost reads
        # `why` as this clamp's lifting condition, so the absence has to reach it in words.
        "ramp": {"size_fraction": size_fraction,
                 "measured": ramp_inp.measured(),
                 "provenance": ramp_inp.block(),
                 "checks": ramp_checks if ramp_inp.measured() else None,
                 "why": ramp_why if ramp_inp.measured() else (
                     f"{ramp_inp.why()} -- ramp held at floor {size_fraction:.2f} BY ABSENCE, "
                     f"not by evaluation. Its only producer is "
                     f"scripts/run_cost_identification.py, which has never published (L1.45).")},
        "effective_size_fraction": round(effective_size, 4),
        "tripwires": tripwires,
        "demoted_to": demoted,
        "stage_gate": {"target": "S1" if stage == "S0" else "S2",
                       "met": gate_met, "why": gate_why,
                       # `measured` is the ONE sibling key of `provenance`, deliberately the same
                       # name the ramp block uses: the desk already carries a five-way stamp-key
                       # zoo (generated/ts/checked/measured/updated) that costs it a lookup every
                       # time, and this fence caught the second name being coined on day one.
                       "measured": promo_inp.measured(),
                       "provenance": promo_inp.block()},
        "freeze": freeze_note,
        "flatten": flatten_note,
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    # ATOMIC write (R0164): this file has TWO writers (the flock'd cadence path and this one) and
    # several readers (run_cashcarry_executor, run_alerts). Plain write_text is truncate-then-
    # write, so a reader landing mid-write -- or a crash in that window -- sees empty/partial
    # JSON. Same-directory temp + `os.replace` (the run_deadman_switch.py idiom): readers see
    # either the whole old report or the whole new one, never a torn file.
    _tmp = _REPORT.with_suffix(".json.tmp")
    _tmp.write_text(json.dumps(report, indent=2), "utf-8")
    os.replace(_tmp, _REPORT)

    # A green S1 gate is the one thing here that needs a HUMAN, so it goes down the existing
    # principal-action channel rather than into a report nobody opens.
    if stage == "S0" and gate_met and not _PRINCIPAL.exists():
        _PRINCIPAL.write_text(
            "S1 (Gate 0) mechanical preconditions are MET -- your sign-off is the only "
            "remaining step. Review data/live_guard.json, then place keys per "
            "docs/playbooks/go_live.md.\n", "utf-8")

    print(f"live_guard stage={stage} armed={venue is not None} rung={rung.name} "
          f"canary={'degraded' if mode.degraded else 'ok'} "
          f"size={effective_size:.3f} tripwires={len(tripwires)}")
    if tripwires:
        print("  TRIPWIRES: " + "; ".join(tripwires))
    print(f"  {rep.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
