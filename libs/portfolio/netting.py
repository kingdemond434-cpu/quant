"""NETTING IS AN EXECUTION ECONOMY. IT IS NOT A RISK DECISION, AND IT SIZES NOTHING.

WHAT IT IS FOR. Eight EURCHF sleeves and three AUDCAD sleeves all send their own order. When two
of them point opposite ways the venue is crossed TWICE to arrive at a position the book could
have reached by not trading at all: two spreads, two commissions, two slippages, and two chances
of a rejection -- paid for a net change of zero. Costs sit inside the growth objective, not
beside it (`docs/GROWTH_GOVERNANCE.md`: commission, spread and swap are paid on every unit of
size, and an uncosted optimum sizes a quantity the desk cannot buy), so removing a round trip
that buys no exposure RAISES E[log W]. That is the whole claim of this module, and it is a
rule-1-positive claim rather than a risk reduction that would owe one.

WHAT IT IS EMPHATICALLY NOT (growth governance, and the principal's standing order given three
times: NEVER REDUCE AGGRESSIVENESS). Netting changes HOW MANY ORDERS reach the venue. It does not
change how much risk the book carries, and it must never become a back door to carrying less:

  * the netted target is the sleeves' own arithmetic sum, not a shrunk, capped or damped version
    of it -- there is no cap, no veto, no confidence floor, no "conditional exception" here;
  * the netted target is checked against EXACTLY the same heat floor, factor caps and survival
    envelope the gross book faced, so netting can never be the reason a book is smaller;
  * rounding is TOWARD ZERO to the venue's volume step, which is the venue's own arithmetic and
    the only direction that cannot hold more than the sleeves asked for. It is not a risk
    control, and where it bites (a net of 0.014 lots at a 0.01 step) the residue is REPORTED
    rather than silently dropped;
  * nothing in this file reads equity, heat, drawdown, ruin or a certificate. It cannot: they are
    not arguments to any function here.

ATTRIBUTION SURVIVES THE NETTING, which is the second reason this is a library and not three
lines in the gateway. When eight sleeves net to one order, the naive implementation attributes
one fill to one sleeve and the other seven vanish from the record -- including the sleeve that
was RIGHT while the book was flat. Every `NettedTarget` therefore carries its full
`contributors` tuple, each with the lots and confidence it asked for, so a fill can be split back
across the sleeves that produced it and a forward clock is never lost to an execution economy.

WHY THE DIAGNOSTIC LANDS BEFORE THE GATEWAY DOES. Wiring this into order placement changes
per-sleeve fills and therefore per-sleeve evidence, which is promotion-firewall ground. So
`desks/mt5/research/netting_report.py` measures and publishes what netting WOULD save, on a
clock, first; the gateway change is principal-gated and separate.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from libs.portfolio.errors import PortfolioError

#: Float-representation repair for the venue step, NOT a licence to round up. `0.03 / 0.01` is
#: 2.9999999999999996 in IEEE 754, and flooring that returns 0.02 -- a step the sleeves did not
#: ask to give up. The epsilon is nine orders of magnitude below one step, so it can never add a
#: whole step to a target; it only stops arithmetic the venue considers exact from losing one.
_STEP_EPS = 1e-9


@dataclass(frozen=True)
class SleeveIntent:
    """One sleeve's own answer to "what should I hold in this symbol", in LOTS.

    `target_lots` is signed (long positive) and is a TARGET, not a delta. `confidence` in [0, 1]
    scales the sleeve's contribution to the net: it is the sleeve's own conviction, supplied by
    whatever produced the intent, and it is never a shrinkage applied from outside. A caller with
    no confidence estimate leaves it at 1.0 and nothing is scaled at all.
    """

    sleeve: str
    symbol: str
    target_lots: float
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not str(self.sleeve).strip():
            raise PortfolioError("SleeveIntent: sleeve name is empty")
        if not str(self.symbol).strip():
            raise PortfolioError(f"SleeveIntent({self.sleeve}): symbol is empty")
        lots = float(self.target_lots)
        if not math.isfinite(lots):
            raise PortfolioError(
                f"SleeveIntent({self.sleeve}): target_lots is {self.target_lots!r}")
        conf = float(self.confidence)
        if not math.isfinite(conf) or conf < 0.0 or conf > 1.0:
            raise PortfolioError(
                f"SleeveIntent({self.sleeve}): confidence {self.confidence!r} is outside [0, 1]. "
                "A confidence above 1 would LEVER the sleeve's own target inside a module that "
                "is not allowed to size, and one below 0 would silently flip its side.")

    @property
    def contribution(self) -> float:
        """The signed lots this intent puts into the net: `target_lots * confidence`."""
        return float(self.target_lots) * float(self.confidence)


@dataclass(frozen=True)
class NettedTarget:
    """What one symbol's sleeves collectively want, and what the venue would actually be sent."""

    symbol: str
    target_lots: float
    gross_lots: float
    contributors: tuple[SleeveIntent, ...] = field(default_factory=tuple)
    volume_step: float = 0.0
    residual_lots: float = 0.0

    @property
    def netting_ratio(self) -> float:
        """`gross / |net|` -- how many lots are crossed for each lot of exposure obtained.

        1.0 means every lot the sleeves asked for reaches the venue and none of it is wasted
        motion. `inf` means the sleeves fully cancelled: the book is flat and the gross lots would
        have crossed the spread for nothing, which is the whole case for netting. A symbol with no
        gross at all returns 0.0 -- there is no motion to be wasteful with, and reporting `inf`
        for a symbol nobody traded would put the strongest possible saving next to an empty row.
        """
        gross = abs(float(self.gross_lots))
        net = abs(float(self.target_lots))
        if net > 0.0:
            return gross / net
        return math.inf if gross > 0.0 else 0.0

    @property
    def n_contributors(self) -> int:
        return len(self.contributors)

    @property
    def orders_saved(self) -> int:
        """Orders the venue does not see: one per contributing sleeve, minus the one net order."""
        sending = sum(1 for c in self.contributors if c.contribution != 0.0)
        return max(sending - (1 if self.target_lots != 0.0 else 0), 0)

    @property
    def lots_not_sent(self) -> float:
        """Gross lots that never cross the spread because the sleeves cancelled each other."""
        return max(abs(float(self.gross_lots)) - abs(float(self.target_lots)), 0.0)


def round_toward_zero(lots: float, step: float) -> float:
    """Snap `lots` DOWN to a whole number of venue volume steps, keeping its sign.

    Toward zero, always: rounding away from zero would hold MORE than every sleeve asked for, and
    a position nobody requested is not an execution economy. See `_STEP_EPS` for why an epsilon is
    present and why it cannot add a step.
    """
    if not math.isfinite(lots):
        raise PortfolioError(f"round_toward_zero: lots is {lots!r}")
    if not math.isfinite(step) or step <= 0.0:
        raise PortfolioError(
            f"round_toward_zero: volume step {step!r} is not a positive number. A missing step is "
            "UNMEASURED (L1.28a) -- it is never 0.01 by assumption, because a venue that steps in "
            "1.0 would silently receive a hundredth of the intended order.")
    units = math.floor(abs(lots) / step + _STEP_EPS)
    if units <= 0:
        return 0.0
    return math.copysign(round(units * step, 12), lots)


def _step_for(symbol: str, volume_step: Mapping[str, float] | float) -> float:
    if isinstance(volume_step, (int, float)):
        step = float(volume_step)
    else:
        raw = volume_step.get(symbol)
        if raw is None:
            raise PortfolioError(
                f"net_intents({symbol}): no volume step. The venue's step is a MEASURED property "
                "of the symbol (universe.json `volume_step`); a symbol without one is UNMEASURED "
                "and its orders are not netted rather than netted against a guess.")
        step = float(raw)
    if not math.isfinite(step) or step <= 0.0:
        raise PortfolioError(f"net_intents({symbol}): volume step {step!r} is not positive")
    return step


def net_intents(
    intents: Iterable[SleeveIntent],
    *,
    volume_step: Mapping[str, float] | float,
) -> tuple[NettedTarget, ...]:
    """Collapse per-sleeve intents into one venue target per symbol, preserving every contributor.

    `volume_step` is the venue's step per symbol (or one step for all of them, which is a test
    convenience and not how a live book is served). A symbol with no step raises rather than
    being netted against an assumed 0.01.

    Returned targets are sorted by symbol; contributors keep their input order, so a report's
    attribution column is stable across runs. `gross_lots` is the RAW sum of |contributions|,
    deliberately unrounded: it is the measurement of what the sleeves asked for, and rounding it
    to the step would quietly change the denominator of every saving claimed downstream.
    """
    by_symbol: dict[str, list[SleeveIntent]] = {}
    for intent in intents:
        if not isinstance(intent, SleeveIntent):
            raise PortfolioError(
                f"net_intents: expected SleeveIntent, got {type(intent).__name__}")
        by_symbol.setdefault(intent.symbol, []).append(intent)

    out: list[NettedTarget] = []
    for symbol in sorted(by_symbol):
        rows = by_symbol[symbol]
        step = _step_for(symbol, volume_step)
        raw_net = math.fsum(row.contribution for row in rows)
        gross = math.fsum(abs(row.contribution) for row in rows)
        net = round_toward_zero(raw_net, step)
        out.append(NettedTarget(
            symbol=symbol,
            target_lots=net,
            gross_lots=gross,
            contributors=tuple(rows),
            volume_step=step,
            residual_lots=round(raw_net - net, 12),
        ))
    return tuple(out)


def attribute_fill(target: NettedTarget, filled_lots: float) -> dict[str, float]:
    """Split a fill back across the sleeves that asked for it, pro rata on |contribution|.

    THE SLEEVE THAT WAS RIGHT WHILE THE BOOK WAS FLAT STILL GETS ITS ROW. A netted order carries
    no sleeve identity at the venue, so without this the eight EURCHF sleeves behind one fill
    become one sleeve with a fill and seven with a silent gap in their forward evidence -- which
    is a promotion-firewall problem, not a bookkeeping one. Pro rata on absolute contribution
    keeps the sign of each sleeve's own request, so a sleeve that asked SHORT is credited short
    even when the net order was long.

    Returns `{}` when there is nothing to attribute. Nothing here sizes: the fill is an input.
    """
    if not math.isfinite(filled_lots):
        raise PortfolioError(f"attribute_fill({target.symbol}): filled_lots is {filled_lots!r}")
    weights = {c.sleeve: abs(c.contribution) for c in target.contributors}
    total = math.fsum(weights.values())
    if total <= 0.0 or filled_lots == 0.0:
        return {}
    share: dict[str, float] = {}
    for contributor in target.contributors:
        signed = math.copysign(1.0, contributor.contribution) if contributor.contribution else 0.0
        share[contributor.sleeve] = (
            share.get(contributor.sleeve, 0.0)
            + abs(filled_lots) * (abs(contributor.contribution) / total) * signed)
    return share


def netting_summary(targets: Sequence[NettedTarget]) -> dict[str, float]:
    """Book-level totals: gross lots asked, net lots sent, orders saved, lots never crossed."""
    gross = math.fsum(abs(t.gross_lots) for t in targets)
    net = math.fsum(abs(t.target_lots) for t in targets)
    return {
        "gross_lots": round(gross, 8),
        "net_lots": round(net, 8),
        "lots_not_sent": round(max(gross - net, 0.0), 8),
        "orders_gross": float(sum(t.n_contributors for t in targets)),
        "orders_saved": float(sum(t.orders_saved for t in targets)),
        "netting_ratio": round(gross / net, 6) if net > 0 else (math.inf if gross > 0 else 0.0),
    }
