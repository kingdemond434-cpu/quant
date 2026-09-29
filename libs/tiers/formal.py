"""FORMAL VERIFICATION OF THE MONEY PATH'S ORCHESTRATION (Tier S layers 31 and 42).

`desks/mt5/research/formal_invariants.py` already PROVES the alpha state machine by exhaustion
and ENFORCES single writers by static enumeration. What it does not reach is the ORDER PROTOCOL:
what happens across an allocator publish, a decision, a send, an acknowledgement, a fill, a crash
and a restart, in every interleaving. That is a concurrency property, and the tool for it is a
model checker: enumerate every reachable state of a finite model and check the invariants in all
of them. This is a small explicit-state checker (breadth-first, full state hashing, shortest
counterexample traces) with the protocol written as data, so the same checker proves the good
protocol and finds the shortest trace that breaks a bad one.

THE MODEL. One sleeve, one broker, a durable journal and a volatile process:

    alloc          the allocator's published fraction (0 or 1 unit)
    cert           the sleeve holds a certificate
    phase          IDLE / DECIDED / SENT / ACKED / FILLED / REJECTED  (per intent)
    journal        what the process wrote durably (intent ids persisted, fills seen)
    broker         intent ids the broker holds, and their fills (idempotent by client id or not)
    alive          whether the process is running
    data_t / now   the newest bar the decision read and the decision clock

ACTIONS: publish(0|1), decide, persist, send, ack, fill, reject, crash, restart, reconcile,
duplicate-deliver, feed-late.

INVARIANTS (each a predicate over a state):

    ZERO_MEANS_NO_ORDER     no intent is sent while the allocator's published fraction is zero
    NO_DUPLICATE_FILL       each logical intent fills at most once at the broker
    EXPOSURE_LIMIT          broker position <= the fraction the allocator published at decide time
    NO_FUTURE_DATA          a decision never reads a bar stamped after its own clock
    CERTIFICATE_REQUIRED    no intent is sent for an uncertified sleeve
    LEGAL_TRANSITIONS       the intent phase only moves forward along its state machine

PROTOCOL KNOBS (the design decisions the proof depends on):

    persist_before_send     write the intent id durably BEFORE sending
    reconcile_on_restart    ask the broker what it holds before re-sending after a restart
    idempotent_client_id    the broker drops a second order with the same client id
    recheck_alloc_at_send   re-read the allocator between decide and send

`check()` returns PROVEN (with the number of states explored) or VIOLATED with the shortest
trace. `desks/mt5/research/tier_s.py` runs the desk's protocol and each single-knob ablation
hourly, so the report shows which design decision each invariant depends on.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from typing import Any

PHASES = ("IDLE", "DECIDED", "SENT", "ACKED", "FILLED", "REJECTED")
_ORDER = {p: i for i, p in enumerate(PHASES)}
LEGAL: dict[str, frozenset[str]] = {
    "IDLE": frozenset({"DECIDED"}),
    "DECIDED": frozenset({"SENT", "IDLE"}),
    "SENT": frozenset({"ACKED", "REJECTED", "FILLED"}),
    "ACKED": frozenset({"FILLED", "REJECTED"}),
    "FILLED": frozenset(),
    "REJECTED": frozenset({"IDLE"}),
}


@dataclass(frozen=True)
class Protocol:
    persist_before_send: bool = True
    reconcile_on_restart: bool = True
    idempotent_client_id: bool = True
    recheck_alloc_at_send: bool = True
    check_cert_at_send: bool = True
    clamp_data_to_clock: bool = True


@dataclass(frozen=True)
class State:
    alloc: int = 1
    alloc_at_decide: int = 0
    cert: bool = True
    phase: str = "IDLE"
    journaled: bool = False
    sends: int = 0           # orders the broker received for this logical intent
    fills: int = 0           # fills the broker executed for it
    position: int = 0
    alive: bool = True
    data_t: int = 0
    now: int = 0
    violated_transition: bool = False
    sent_while_zero: bool = False
    sent_uncertified: bool = False
    publishes: int = 0
    crashes: int = 0
    late_feeds: int = 0
    revoked: bool = False


Invariant = Callable[[State], bool]

INVARIANTS: dict[str, Invariant] = {
    "ZERO_MEANS_NO_ORDER": lambda s: not s.sent_while_zero,
    "NO_DUPLICATE_FILL": lambda s: s.fills <= 1,
    "EXPOSURE_LIMIT": lambda s: s.position <= s.alloc_at_decide or s.position == 0,
    "NO_FUTURE_DATA": lambda s: s.data_t <= s.now,
    "CERTIFICATE_REQUIRED": lambda s: not s.sent_uncertified,
    "LEGAL_TRANSITIONS": lambda s: not s.violated_transition,
}


def _move(s: State, to: str, **kw: Any) -> State:
    bad = to not in LEGAL[s.phase]
    return replace(s, phase=to, violated_transition=s.violated_transition or bad, **kw)


def successors(s: State, p: Protocol, *, max_publish: int = 2, max_crash: int = 2,
               max_late: int = 1) -> Iterator[tuple[str, State]]:
    # environment: the allocator may republish 0 or 1 at any time (bounded)
    if s.publishes < max_publish:
        for a in (0, 1):
            if a != s.alloc:
                yield f"publish({a})", replace(s, alloc=a, publishes=s.publishes + 1)
    # a feed may deliver a bar stamped after the clock (bounded)
    if s.late_feeds < max_late:
        yield "feed_late", replace(s, late_feeds=s.late_feeds + 1,
                                   data_t=min(s.now + 1, 3) if not p.clamp_data_to_clock
                                   else s.data_t)
    # the certificate may be revoked at any time (once)
    if s.cert and not s.revoked:
        yield "revoke_cert", replace(s, cert=False, revoked=True)
    if s.alive and s.crashes < max_crash:
        yield "crash", replace(s, alive=False, crashes=s.crashes + 1)
    if not s.alive:
        # RESTART: the volatile phase is lost and the durable journal survives. This is not a
        # transition of the intent machine (it is the machine being rebuilt), so it is exempt
        # from LEGAL_TRANSITIONS.
        if s.phase == "FILLED":
            ph = "FILLED"
        elif p.reconcile_on_restart and s.sends > 0:
            ph = "FILLED" if s.fills else "SENT"
        elif s.journaled:
            ph = "DECIDED"          # the journal says "send this" and nobody asked the broker
        else:
            ph = "IDLE"             # nothing durable: the process will decide afresh
        yield "restart", replace(s, alive=True, phase=ph)
        return
    if s.phase == "IDLE" and s.alloc > 0 and s.position == 0:
        # the clock is abstracted to {0, 1, 2}: only "before / at / after the decision" matters
        tick = min(s.now + 1, 2)
        yield "decide", _move(s, "DECIDED", alloc_at_decide=s.alloc, now=tick,
                              data_t=min(s.data_t, tick) if p.clamp_data_to_clock
                              else s.data_t)
    if s.phase == "DECIDED" and not s.journaled:
        yield "persist", replace(s, journaled=True)
    if s.phase == "DECIDED" and (s.journaled or not p.persist_before_send):
        if p.recheck_alloc_at_send and s.alloc == 0:
            yield "abandon_zero", _move(s, "IDLE", journaled=False)
        elif p.check_cert_at_send and not s.cert:
            yield "abandon_uncertified", _move(s, "IDLE", journaled=False)
        else:
            dup = s.sends > 0 and p.idempotent_client_id and s.journaled
            yield "send", _move(s, "SENT", sends=s.sends + (0 if dup else 1),
                                sent_while_zero=s.sent_while_zero or s.alloc == 0,
                                sent_uncertified=s.sent_uncertified or not s.cert)
    if s.phase == "SENT" and not s.journaled:
        yield "persist_late", replace(s, journaled=True)
    if s.phase in ("SENT", "ACKED") and s.sends > s.fills:
        if s.phase == "SENT":
            yield "ack", _move(s, "ACKED")
        yield "fill", _move(s, "FILLED", fills=s.fills + 1, position=s.position + 1)
        yield "reject", _move(s, "REJECTED", sends=s.sends - 1)
    # the broker executing a second order it holds (a non-idempotent resend) after the first
    if s.phase == "FILLED" and s.sends > s.fills:
        yield "broker_fills_duplicate", replace(s, fills=s.fills + 1, position=s.position + 1)
    if s.phase == "REJECTED":
        yield "reset", _move(s, "IDLE", journaled=False)


def check(p: Protocol, *, init: State | None = None, max_states: int = 200_000
          ) -> dict[str, Any]:
    """BFS over every reachable state; the first violation found has the shortest trace."""
    start = init or State()
    seen: dict[State, tuple[State | None, str]] = {start: (None, "init")}
    q: deque[State] = deque([start])
    violations: dict[str, list[str]] = {}
    while q and len(seen) < max_states:
        s = q.popleft()
        for name, inv in INVARIANTS.items():
            if name not in violations and not inv(s):
                trace = []
                cur: State | None = s
                while cur is not None:
                    prev, act = seen[cur]
                    trace.append(act)
                    cur = prev
                violations[name] = list(reversed(trace))
        for act, nxt in successors(s, p):
            if nxt not in seen:
                seen[nxt] = (s, act)
                q.append(nxt)
    complete = not q
    per = {name: ({"verdict": "VIOLATED", "trace": violations[name]} if name in violations
                  else {"verdict": "PROVEN" if complete else "BOUNDED"})
           for name in INVARIANTS}
    return {"protocol": p.__dict__, "states": len(seen), "complete": complete,
            "invariants": per,
            "all_proven": complete and not violations}


def ablations(base: Protocol | None = None) -> dict[str, Any]:
    """The desk's protocol, then each knob switched off: which invariant rests on which knob."""
    base = base or Protocol()
    out = {"desk": check(base)}
    knobs = [k for k, v in base.__dict__.items() if v]
    for knob in knobs:
        out[f"without_{knob}"] = check(replace(base, **{knob: False}))
    # pairs: an invariant protected by EITHER of two mechanisms only shows up here
    for i, a in enumerate(knobs):
        for b in knobs[i + 1:]:
            out[f"without_{a}+{b}"] = check(replace(base, **{a: False, b: False}))
    depends: dict[str, list[str]] = {}
    for label, res in out.items():
        if label == "desk":
            continue
        for inv, v in res["invariants"].items():
            if v["verdict"] != "VIOLATED":
                continue
            removed = label.removeprefix("without_")
            # report a pair only when neither single ablation already breaks the invariant
            if "+" in removed and any(x in depends.get(inv, []) for x in removed.split("+")):
                continue
            depends.setdefault(inv, []).append(removed)
    return {"runs": out, "depends_on": depends,
            "desk_all_proven": bool(out["desk"]["all_proven"])}


def phase_rank(p: str) -> int:
    return _ORDER[p]
