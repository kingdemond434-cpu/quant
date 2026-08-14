"""THE DISCRETIONARY SLEEVE -- a PRE-REGISTERED rule, a risk process, and a journal of every call.

WHAT WAS MISSING AND WHAT WAS NOT. `run_discretionary_hunt` finds candidate edges and
`run_discretionary_max` optimises the sleeve's hit rate against a 38% target. Both are real. But
NOTHING BETWEEN THEM COULD TRADE: there is no signal-to-order path anywhere outside cash-carry, and
no journal, so a discretionary trade left no record and the hit rate the optimiser targets was
measured on nothing.

**THE RULE IS AN INPUT, NEVER SOMETHING THIS MODULE INVENTS.** The hunt produces prose -- "a
situation a skilled human recognises on a chart and in the flow" -- and prose is not an entry
condition. Turning that into money requires somebody to WRITE THE RULE DOWN FIRST, in code, with
its direction, its trigger, its exit and its invalidation stated before any live bar arrives. That
is the whole pre-registration property, and a module that guessed the rule on the caller's behalf
would destroy it silently while looking helpful.

**THE RISK PROCESS IS THE PART THAT TRANSFERS, AND IT IS FIXED HERE RATHER THAN PER-TRADE**
(III.15: risk process is the highest-transfer category from real traders, because it is mechanical
and testable, and it is where operators genuinely differ). Fixed-fractional risk per trade, a hard
daily loss cap, a cap on concurrent positions, and NO SIZE PROGRESSION AFTER A LOSS -- the last is
the single most important line in this file, because averaging down and martingale progression are
what produce the long smooth equity curves that dominate leaderboards and end in one terminal loss.

**IT PLACES NOTHING.** It returns an intent. The executor places, the risk kernel bounds, and the
deadman can stop everything regardless of what this concluded. Same separation the carry path uses,
for the same reason: a strategy that could place its own orders is a strategy whose sizing bugs
reach the venue directly.

**EVERY DECISION IS JOURNALLED, INCLUDING THE REFUSALS.** A sleeve that records only its trades
cannot distinguish "the rule fired twice this week" from "the rule fired forty times and the risk
process blocked thirty-eight" -- and those are completely different strategies wearing one hit
rate. The refusals are also the only way to notice that a cap is binding so often it has become
the strategy.

Stdlib only. import from libs.execution.discretionary_sleeve.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "DAILY_LOSS_CAP_FRAC",
    "MAX_CONCURRENT",
    "RISK_PER_TRADE_FRAC",
    "Decision",
    "RuleSignal",
    "SleeveState",
    "journal",
    "size_and_check",
]

#: Fraction of equity risked per trade -- risk meaning the distance to the stop, not the notional.
#: FIXED-FRACTIONAL AND FIXED HERE: a risk fraction that varies per trade is a discretionary sizing
#: decision, and discretionary sizing is where a hit-rate edge is most often given back.
RISK_PER_TRADE_FRAC = 0.01

#: The day stops when cumulative realised loss reaches this fraction of starting equity. A daily
#: cap is the one rule that reliably survives contact with a losing streak, because it bounds the
#: damage a bad DAY can do without requiring anyone to judge, mid-drawdown, whether to keep going.
DAILY_LOSS_CAP_FRAC = 0.03

#: How many discretionary positions may be open at once. Bounds correlation as much as exposure:
#: three simultaneous crypto longs are close to one position at three times the size.
MAX_CONCURRENT = 2


@dataclass(frozen=True)
class RuleSignal:
    """One firing of a PRE-REGISTERED rule. Every field is stated before the bar, never after.

    `stop_price` is required and is not a formality: without it there is no risk distance, so
    there is no fixed-fractional size, and "how much do we buy" collapses back into a judgement
    call -- which is the thing this sleeve exists to remove from the loop.
    """

    rule_id: str
    symbol: str
    side: str                      # "BUY" or "SELL"
    entry_price: float
    stop_price: float
    #: WHO IS FORCED TO TRADE AGAINST YOU. Carried from the hunt's own admission criterion: a
    #: candidate that cannot name a forced participant is a pattern, not a mechanism.
    forced_participant: str = ""
    target_price: float | None = None
    note: str = ""


@dataclass
class SleeveState:
    """What the sleeve knows about today. Supplied by the caller from real book state."""

    equity_usd: float
    realised_pnl_today_usd: float = 0.0
    open_positions: int = 0
    #: Consecutive losses, carried ONLY so the sleeve can prove it did not react to them.
    loss_streak: int = 0


@dataclass(frozen=True)
class Decision:
    """TAKE / REFUSE, the size, and the reason -- which is the part read later."""

    take: bool
    qty: float
    risk_usd: float
    why: str
    signal: dict[str, Any] = field(default_factory=dict)

    @property
    def refused(self) -> bool:
        return not self.take


def size_and_check(sig: RuleSignal, state: SleeveState, *,
                   risk_frac: float = RISK_PER_TRADE_FRAC,
                   daily_cap_frac: float = DAILY_LOSS_CAP_FRAC,
                   max_concurrent: int = MAX_CONCURRENT,
                   min_notional_usd: float | None = None) -> Decision:
    """Size this signal and rule on it. Every gate is a REFUSAL that must pass.

    NO SCORING. A weighted score lets a strong number on one axis buy past a hard requirement on
    another, which is exactly how a daily loss cap stops being a cap.
    """
    s = asdict(sig)

    if sig.side not in ("BUY", "SELL"):
        return Decision(False, 0.0, 0.0, f"side {sig.side!r} is neither BUY nor SELL", s)
    risk_per_unit = abs(float(sig.entry_price) - float(sig.stop_price))
    if risk_per_unit <= 0:
        return Decision(False, 0.0, 0.0, (
            "entry and stop are equal, so the risk distance is zero. A position with no risk "
            "distance has no fixed-fractional size -- and dividing by it would return an infinite "
            "quantity, which is the single most expensive arithmetic error available here"), s)
    if float(state.equity_usd) <= 0:
        return Decision(False, 0.0, 0.0, "equity is zero or unmeasured -- nothing to risk", s)

    # THE DAILY CAP, CHECKED BEFORE SIZING so a losing day cannot be argued past by a good setup.
    loss_today = -min(0.0, float(state.realised_pnl_today_usd))
    cap = daily_cap_frac * float(state.equity_usd)
    if loss_today >= cap:
        return Decision(False, 0.0, 0.0, (
            f"daily loss cap reached: ${loss_today:,.2f} of ${cap:,.2f} ({daily_cap_frac:.1%} of "
            "equity). The day is over regardless of how good this setup looks. A cap that can be "
            "argued past by the next opportunity is not a cap, and the moment it is most tempting "
            "to override is exactly the moment it is doing its job"), s)

    if int(state.open_positions) >= int(max_concurrent):
        return Decision(False, 0.0, 0.0, (
            f"{state.open_positions} positions already open (cap {max_concurrent}). This bounds "
            "CORRELATION as much as exposure: three simultaneous crypto longs are close to one "
            "position at three times the size"), s)

    # SIZE. Risk fraction is CONSTANT -- it does not rise after a loss and does not fall after a
    # win. THE MOST IMPORTANT LINE IN THIS FILE: progression after a loss (martingale, averaging
    # down, "recovering" the last trade) is what produces the long smooth equity curves that
    # dominate short leaderboards and end in one terminal loss (III.15). The loss streak is carried
    # in state ONLY so this refusal to react to it is auditable.
    risk_usd = risk_frac * float(state.equity_usd)
    qty = risk_usd / risk_per_unit
    notional = qty * float(sig.entry_price)

    if min_notional_usd is not None and notional < float(min_notional_usd):
        return Decision(False, 0.0, risk_usd, (
            f"sized notional ${notional:,.2f} is below the venue minimum "
            f"${float(min_notional_usd):,.2f}. Reaching it would require risking more than "
            f"{risk_frac:.1%} of equity on one trade -- so this is a statement that the BOOK is "
            "too small for this stop distance, not that the setup is wrong. Widening the risk "
            "fraction to fit the venue is the same error as rounding a clip up to a minimum: it "
            "breaches the limit silently, in the direction that loses more"), s)

    return Decision(True, round(qty, 8), round(risk_usd, 2), (
        f"{sig.side} {qty:.8f} {sig.symbol} at {sig.entry_price} with a stop at {sig.stop_price}: "
        f"${risk_usd:,.2f} at risk ({risk_frac:.1%} of ${float(state.equity_usd):,.2f}), notional "
        f"${notional:,.2f}. Risk fraction is CONSTANT -- unchanged by the {state.loss_streak} "
        f"consecutive loss(es) on record, because sizing that reacts to the last trade is how a "
        f"hit-rate edge is given back. Rule {sig.rule_id}"
        + (f"; forced participant: {sig.forced_participant}" if sig.forced_participant else "")), s)


def journal(decision: Decision, path: Path | str, *, now: datetime | None = None) -> dict[str, Any]:
    """Append one decision -- TAKEN OR REFUSED -- to the sleeve's journal. Returns the row.

    REFUSALS ARE RECORDED AND THAT IS NOT BOOKKEEPING. A sleeve that journals only its trades
    cannot tell "the rule fired twice this week" from "the rule fired forty times and the risk
    process blocked thirty-eight", and those are different strategies sharing one hit rate. It is
    also the only way to notice that a cap is binding so often it has quietly BECOME the strategy.

    APPEND-ONLY JSONL: a journal that can be rewritten is not evidence, for the same reason a
    forward clock whose history can be edited is not evidence.
    """
    row = {
        "at": (now or datetime.now(tz=UTC)).isoformat(),
        "taken": bool(decision.take),
        "qty": decision.qty,
        "risk_usd": decision.risk_usd,
        "why": decision.why,
        **decision.signal,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row
