"""EXECUTION OPPORTUNITY SURFACE — a theoretically profitable signal that is not tradeable.

THE GAP THIS CLOSES. Every validated signal on this desk carries an expected edge in bps. Nothing
carries the four numbers that decide whether that edge survives contact with a book::

    EV(MAKER)   post and wait. Earn the spread and the rebate, risk not being filled, and risk
                being filled only when you are wrong -- which is the same thing as adverse
                selection and is the reason a high maker share is not an achievement.
    EV(TAKER)   cross now. Pay the spread and the fee, and keep the whole signal.
    EV(WAIT)    do nothing this instant and re-evaluate. Only positive when the edge decays
                slowly relative to how fast the book is improving.
    EV(NO_TRADE) zero, and it wins more often than any desk expects.

**THE MAKER TRAP, WHICH IS WHY THIS CANNOT BE A HEURISTIC.** A resting order is filled by whoever
wanted to trade against it, and near-term that is disproportionately someone with better
information. So the fills a maker gets are a biased sample of the fills it wanted: the good ones
are the trades that did not happen. `maker_ev` therefore charges adverse selection against the
FILLED fraction, and a maker strategy with a high fill rate in fast markets is usually being
selected against rather than being liked.

**ALPHA HALF-LIFE IS THE VARIABLE THAT DECIDES EVERYTHING.** A signal with a 30-second half-life
cannot wait 40 seconds in a queue -- by the time it fills, most of what it knew is public. A signal
with a 6-hour half-life should almost never cross. The same book, the same spread and the same
queue produce opposite answers for those two, which is precisely why a fixed execution policy is
wrong for one of them.

**OPTIMISES REALISED E[log W], NOT MAKER SHARE.** Maker percentage is a gameable proxy: it is
maximised by never trading when it is urgent, which is when the edge is largest.

Prices the choice. Places nothing -- `libs/execution/maker.py` owns the actual order path.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "POLICIES",
    "BookState",
    "SignalState",
    "best_policy",
    "maker_ev",
    "summarise",
    "taker_ev",
    "wait_ev",
]

#: The four things that can be done with a signal right now. NO_TRADE is a first-class answer and
#: wins more often than any desk expects.
POLICIES: tuple[str, ...] = ("MAKER", "TAKER", "WAIT", "NO_TRADE")


@dataclass(frozen=True)
class BookState:
    """The venue as it is at this instant. Every cost in bps of notional."""

    half_spread_bps: float = 0.0
    #: Probability a resting order at the touch is filled within the signal's usable window.
    #: 0 = UNMEASURED, which makes maker EV unpriceable rather than zero.
    fill_probability: float = 0.0
    #: Expected adverse move, in bps, CONDITIONAL on the maker order being filled. The whole maker
    #: trap in one field: it is not the average move, it is the move given that someone took you.
    adverse_selection_bps: float = 0.0
    #: Fees. Maker is frequently negative (a rebate) and that is not a reason to prefer maker.
    maker_fee_bps: float = 0.0
    taker_fee_bps: float = 0.0
    #: Market impact of crossing at the intended size, in bps.
    impact_bps: float = 0.0
    #: Expected queue wait in seconds, and how fast the book is repairing (0 = not repairing).
    expected_queue_seconds: float = 0.0
    spread_recovery_bps_per_second: float = 0.0


@dataclass(frozen=True)
class SignalState:
    """The signal, and the one property that decides which execution policy is correct."""

    name: str
    #: Expected gross edge in bps before any execution cost. 0 = UNMEASURED.
    edge_bps: float = 0.0
    #: Seconds over which half the edge is gone. THE DECIDING VARIABLE. 0 = unmeasured, and every
    #: policy is then unpriceable -- an execution decision without a half-life is a guess.
    half_life_seconds: float = 0.0
    #: Posterior width on the edge, in bps. Charged once, to every policy that trades.
    edge_sigma_bps: float = 0.0

    @property
    def measured(self) -> bool:
        return self.edge_bps != 0.0 and self.half_life_seconds > 0


def _decayed(s: SignalState, seconds: float) -> float:
    if s.half_life_seconds <= 0:
        return s.edge_bps
    return float(s.edge_bps * 0.5 ** (max(0.0, seconds) / s.half_life_seconds))


def taker_ev(s: SignalState, b: BookState) -> tuple[float | None, str]:
    """Cross now: keep the whole signal, pay the whole cost."""
    if not s.measured:
        return None, f"{s.name}: no edge or no half-life recorded -- crossing cannot be priced"
    shrunk = s.edge_bps - s.edge_sigma_bps
    cost = b.half_spread_bps + b.taker_fee_bps + b.impact_bps
    ev = shrunk - cost
    return ev, (
        f"{s.name} TAKER: {shrunk:.2f}bp edge less {b.half_spread_bps:.2f} half-spread, "
        f"{b.taker_fee_bps:.2f} fee, {b.impact_bps:.2f} impact => {ev:+.2f}bp. The signal is "
        "captured in full; nothing decays because nothing waits")


def maker_ev(s: SignalState, b: BookState) -> tuple[float | None, str]:
    """Post and wait. Earn the spread when filled, and pay adverse selection ON THE FILLS.

    THE ASYMMETRY THAT MAKES THIS NOT A SPREAD REBATE. The unfilled fraction is not free: it is the
    trades the desk wanted and did not get, and they are disproportionately the ones where the
    signal was RIGHT and the market moved away. So the expectation is taken over fills only, the
    edge is decayed by the queue wait, and adverse selection is charged in full against them.
    """
    if not s.measured:
        return None, f"{s.name}: no edge or no half-life recorded -- posting cannot be priced"
    if b.fill_probability <= 0:
        return None, (
            f"{s.name}: fill probability UNMEASURED, so maker EV is not zero -- it is unknown. A "
            "maker policy priced without a fill rate assumes it always gets filled, which is the "
            "assumption a passive order most reliably violates")
    p = max(0.0, min(1.0, b.fill_probability))
    edge_at_fill = _decayed(s, b.expected_queue_seconds) - s.edge_sigma_bps
    per_fill = edge_at_fill + b.half_spread_bps - b.maker_fee_bps - b.adverse_selection_bps
    ev = p * per_fill
    decay_note = ""
    if b.expected_queue_seconds > 0 and s.half_life_seconds > 0:
        kept = 0.5 ** (b.expected_queue_seconds / s.half_life_seconds)
        decay_note = (f" Waiting {b.expected_queue_seconds:g}s against a {s.half_life_seconds:g}s "
                      f"half-life keeps {kept:.0%} of the edge")
        if kept < 0.5:
            decay_note += (" -- most of what this signal knew is public by the time it fills, and "
                           "the queue is where the edge went")
    return ev, (
        f"{s.name} MAKER: {p:.0%} fill x ({edge_at_fill:.2f}bp edge at fill + "
        f"{b.half_spread_bps:.2f} spread earned - {b.maker_fee_bps:.2f} fee - "
        f"{b.adverse_selection_bps:.2f} adverse selection) => {ev:+.2f}bp." + decay_note +
        ". Adverse selection is charged against the FILLED fraction only, because the fills a "
        "resting order gets are a biased sample of the fills it wanted")


def wait_ev(s: SignalState, b: BookState, *, wait_seconds: float = 5.0) -> tuple[float | None, str]:
    """Do nothing this instant, then re-evaluate against a repaired book.

    Only positive when the book is improving FASTER than the edge is decaying. That is a real
    state -- it is what the seconds after a liquidation cascade look like -- and it is the one
    execution answer no desk reaches by instinct, because doing nothing does not feel like a
    decision.
    """
    if not s.measured:
        return None, f"{s.name}: unpriceable without an edge and a half-life"
    future_spread = max(0.0, b.half_spread_bps - b.spread_recovery_bps_per_second * wait_seconds)
    saved = b.half_spread_bps - future_spread
    lost = s.edge_bps - _decayed(s, wait_seconds)
    ev_now, _ = taker_ev(s, b)
    ev = (ev_now or 0.0) + saved - lost
    return ev, (
        f"{s.name} WAIT {wait_seconds:g}s: spread repairs {saved:.2f}bp while the edge decays "
        f"{lost:.2f}bp => {ev:+.2f}bp against {ev_now:+.2f}bp crossing now. "
        + ("The book is repairing faster than the signal is decaying -- patience is the trade"
           if saved > lost else
           "The signal decays faster than the book repairs, so waiting is a slow way of paying "
           "the spread anyway"))


def best_policy(s: SignalState, b: BookState, *,
                wait_seconds: float = 5.0) -> tuple[str, str, dict[str, float | None]]:
    """(policy, why, evs). NO_TRADE when nothing clears zero -- and it frequently does not."""
    evs: dict[str, float | None] = {
        "TAKER": taker_ev(s, b)[0],
        "MAKER": maker_ev(s, b)[0],
        "WAIT": wait_ev(s, b, wait_seconds=wait_seconds)[0],
        "NO_TRADE": 0.0,
    }
    priced = {k: v for k, v in evs.items() if v is not None}
    if set(priced) == {"NO_TRADE"}:
        return "NO_TRADE", (
            f"{s.name}: no policy could be priced -- "
            + (taker_ev(s, b)[1] if not s.measured else maker_ev(s, b)[1])
            + ". An unpriceable execution decision defaults to NOT trading, because the cost of "
              "abstaining is bounded and the cost of crossing blind is not"), evs
    best = max(priced, key=lambda k: priced[k])
    if best == "NO_TRADE":
        return "NO_TRADE", (
            f"{s.name}: every policy is negative after costs (taker {evs['TAKER']}, maker "
            f"{evs['MAKER']}, wait {evs['WAIT']}). The signal may be real and is NOT ECONOMICALLY "
            "TRADEABLE at this book -- which is a finding about execution, not about the "
            "research"), evs
    return best, (
        f"{s.name}: {best} at {priced[best]:+.2f}bp"
        + (f", against {priced['TAKER']:+.2f}bp crossing" if "TAKER" in priced
           and best != "TAKER" else "")
        + ". Chosen on expected bps, never on maker share -- maker percentage is maximised by "
          "declining to trade when it is urgent, which is when the edge is largest"), evs


def summarise(pairs: list[tuple[SignalState, BookState]]) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not pairs:
        return {"signals": 0, "headline": (
            "no signal/book pairs recorded -- whether any validated signal on this desk is "
            "actually tradeable after spread, fill hazard and adverse selection is UNMEASURED")}
    rows = []
    for s, b in pairs:
        pol, why, evs = best_policy(s, b)
        rows.append({"signal": s.name, "policy": pol, "why": why,
                     "edge_bps": s.edge_bps, "half_life_seconds": s.half_life_seconds,
                     "ev_bps": {k: (None if v is None else round(v, 4)) for k, v in evs.items()}})
    untradeable = [r for r in rows if r["policy"] == "NO_TRADE"]
    return {
        "signals": len(pairs),
        "rows": rows,
        "not_economically_tradeable": len(untradeable),
        "headline": (
            f"{len(untradeable)} of {len(pairs)} signal(s) are NOT ECONOMICALLY TRADEABLE at the "
            f"current book: {[r['signal'] for r in untradeable[:3]]}. That is a finding about "
            "execution, and a validated signal that cannot be executed contributes exactly nothing"
            if untradeable else
            f"all {len(pairs)} signal(s) clear their execution costs; "
            f"{sum(1 for r in rows if r['policy'] == 'MAKER')} favour posting"),
        "note": ("Optimises expected bps and therefore realised E[log W], never maker share -- "
                 "maker percentage is a gameable proxy maximised by declining to trade when it is "
                 "urgent. Adverse selection is charged against FILLED orders only: the fills a "
                 "resting order receives are a biased sample of the fills it wanted, because the "
                 "good ones are the trades that did not happen."),
    }
