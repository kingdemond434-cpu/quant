"""ARCHITECTURE FAILURE WORLDS: world-search beyond knob ablations (Tier S layer 39).

`libs/tiers/formal.py` proves the order protocol and then switches its DESIGN knobs off one and two
at a time, which answers "which decision does each invariant rest on". It never asks the other
half of the question: with every design decision in place, which WORLDS break the protocol
anyway? A knob is something the desk chose; a world is something the venue, the operating system
or the network does to it. The two are different searches, and only this one finds a failure the
design cannot fix by being switched back on.

A world is a set of FAULTS, each a thing the environment can do that the proof's model does not
let it do:

    venue_ignores_client_id   the broker accepts two orders with one client id (MT5 does not
                              deduplicate by comment -- idempotence is the desk's hope, not the
                              venue's contract)
    stale_reconcile           after a restart the broker's answer lags: it misses the last send
    torn_journal              a crash loses the journal write that was not yet fsynced
    network_duplicate         the network delivers one send twice
    late_fill_after_reject    the broker reports a reject and fills the order anyway
    recheck_send_race         the allocator/certificate re-check and the send are two steps, and
                              the environment may act between them (a TOCTOU window)
    clock_skew                the clamp compares bars with a clock that is one tick behind the
                              feed's (the venue runs UTC+2/+3, the process UTC)
    deep_crash                three crashes and three publishes instead of two

`search()` enumerates fault sets by increasing size, model-checks the DESK'S protocol (every knob
on) in each world with the same BFS and invariants as `formal.check`, and keeps the MINIMAL
failing worlds: a world is reported only if no proper subset of its faults already fails, so each
finding names exactly the faults that are jointly necessary. Supersets of a minimal failing world
are skipped, never re-reported. Every finding carries the shortest counterexample trace, which
`libs/tiers/core_drive.py` then replays against the real `decision_core`.

Research-side only: nothing here reads or writes the gateway, a sleeve, a size or an order.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from typing import Any

from libs.tiers import formal

FAULTS: tuple[str, ...] = (
    "venue_ignores_client_id", "stale_reconcile", "torn_journal", "network_duplicate",
    "late_fill_after_reject", "recheck_send_race", "clock_skew", "deep_crash",
)


@dataclass(frozen=True)
class WState:
    s: formal.State
    armed: bool = False          # recheck passed, transmit pending (recheck_send_race only)
    stale_used: int = 0
    torn_used: int = 0
    dup_used: int = 0
    late_fill_used: int = 0
    skew_used: int = 0


def _send_effect(s: formal.State, p: formal.Protocol) -> formal.State:
    dup = s.sends > 0 and p.idempotent_client_id and s.journaled
    return formal._move(s, "SENT", sends=s.sends + (0 if dup else 1),
                        sent_while_zero=s.sent_while_zero or s.alloc == 0,
                        sent_uncertified=s.sent_uncertified or not s.cert)


def successors(w: WState, p: formal.Protocol, faults: frozenset[str]
               ) -> Iterator[tuple[str, WState]]:
    s = w.s
    eff = replace(p, idempotent_client_id=False) if "venue_ignores_client_id" in faults else p
    deep = "deep_crash" in faults
    base = formal.successors(s, eff, max_publish=3 if deep else 2, max_crash=3 if deep else 2)
    race = "recheck_send_race" in faults
    for act, nxt in base:
        if act == "crash":
            yield act, replace(w, s=nxt, armed=False)
            continue
        if race and act in ("send", "abandon_zero", "abandon_uncertified"):
            if w.armed:
                continue                     # already rechecked: the transmit step below sends
            if act == "send":
                # the re-check passed; the send happens on a LATER step
                yield "recheck_ok", replace(w, armed=True)
                continue
        yield act, replace(w, s=nxt, armed=w.armed and nxt.phase == s.phase)
    if not s.alive:
        if "stale_reconcile" in faults and w.stale_used < 1 and s.sends > 0 \
                and s.phase != "FILLED":
            ph = "DECIDED" if s.journaled else "IDLE"
            yield "restart_stale_reconcile", replace(
                w, s=replace(s, alive=True, phase=ph), stale_used=w.stale_used + 1)
        return
    if race and w.armed and s.phase == "DECIDED":
        yield "transmit", replace(w, s=_send_effect(s, eff), armed=False)
    if "torn_journal" in faults and w.torn_used < 1 and s.journaled \
            and s.crashes < (3 if deep else 2):
        yield "crash_torn_journal", replace(
            w, s=replace(s, alive=False, crashes=s.crashes + 1, journaled=False),
            armed=False, torn_used=w.torn_used + 1)
    if "network_duplicate" in faults and w.dup_used < 1 and s.phase in ("SENT", "ACKED") \
            and not eff.idempotent_client_id:
        yield "network_duplicate", replace(w, s=replace(s, sends=s.sends + 1),
                                           dup_used=w.dup_used + 1)
    if "late_fill_after_reject" in faults and w.late_fill_used < 1 and s.phase == "REJECTED":
        yield "late_fill_after_reject", replace(
            w, s=replace(s, fills=s.fills + 1, position=s.position + 1),
            late_fill_used=w.late_fill_used + 1)
    if "clock_skew" in faults and w.skew_used < 1:
        yield "feed_skewed", replace(w, s=replace(s, data_t=min(s.now + 1, 3)),
                                     skew_used=w.skew_used + 1)


def check_world(faults: Sequence[str], p: formal.Protocol | None = None, *,
                max_states: int = 200_000) -> dict[str, Any]:
    """BFS over one world; the first violation of each invariant has the shortest trace."""
    p = p or formal.Protocol()
    fs = frozenset(faults)
    start = WState(formal.State())
    seen: dict[WState, tuple[WState | None, str]] = {start: (None, "init")}
    q: deque[WState] = deque([start])
    violations: dict[str, list[str]] = {}
    while q and len(seen) < max_states:
        w = q.popleft()
        for name, inv in formal.INVARIANTS.items():
            if name not in violations and not inv(w.s):
                trace: list[str] = []
                cur: WState | None = w
                while cur is not None:
                    prev, act = seen[cur]
                    trace.append(act)
                    cur = prev
                violations[name] = list(reversed(trace))
        for act, nxt in successors(w, p, fs):
            if nxt not in seen:
                seen[nxt] = (w, act)
                q.append(nxt)
    complete = not q
    return {"faults": sorted(fs), "states": len(seen), "complete": complete,
            "violations": {k: violations[k] for k in sorted(violations)},
            "verdict": ("VIOLATED" if violations else "HOLDS" if complete else "BOUNDED")}


def search(faults: Sequence[str] = FAULTS, *, max_size: int = 3, max_worlds: int = 200,
           p: formal.Protocol | None = None) -> dict[str, Any]:
    """Enumerate fault sets by size; keep the MINIMAL failing worlds per invariant."""
    p = p or formal.Protocol()
    minimal: list[dict[str, Any]] = []
    #: (fault set, invariant) pairs already explained by a smaller world
    explained: list[tuple[frozenset[str], str]] = []
    searched = 0
    holds: list[list[str]] = []
    bounded = 0
    for k in range(1, max_size + 1):
        for combo in combinations(sorted(faults), k):
            if searched >= max_worlds:
                break
            fs = frozenset(combo)
            res = check_world(combo, p)
            searched += 1
            bounded += int(not res["complete"])
            new = {inv: tr for inv, tr in res["violations"].items()
                   if not any(sub <= fs and inv == i for sub, i in explained)}
            for inv, tr in new.items():
                explained.append((fs, inv))
                minimal.append({"faults": sorted(fs), "invariant": inv, "trace": tr,
                                "trace_len": len(tr), "states": res["states"]})
            if res["verdict"] == "HOLDS":
                holds.append(sorted(fs))
    single = {f: next((m["invariant"] for m in minimal if m["faults"] == [f]), None)
              for f in faults}
    return {"protocol": p.__dict__, "faults": list(faults), "worlds_searched": searched,
            "worlds_bounded": bounded, "max_size": max_size,
            "minimal_failing_worlds": minimal, "n_failing": len(minimal),
            "invariants_broken": sorted({m["invariant"] for m in minimal}),
            "single_fault": single, "worlds_holding": len(holds),
            "note": "every knob of the desk's protocol is ON in every world; a finding here is a "
                    "failure the design cannot fix by switching a knob back on"}
