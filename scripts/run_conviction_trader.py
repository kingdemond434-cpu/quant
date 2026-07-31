#!/usr/bin/env python3
"""CONVICTION SLEEVE (R0125) -- Claude as an AGGRESSIVE leveraged directional trader, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31, with an MT5 screenshot: a leveraged XAUUSD short, +60% in 12h):
*"the Binance equivalent to this -- aggressive, AI shouldn't be too calculative and earn less
than a manual trader."* And then the mechanism, in the principal's own words: *"use calculated SL
to prevent it and put trades until the trend and swing hits, minimising downside and maximising
upside."*

CORRECTION OF RECORD (2026-07-31). This file previously described the screenshot as a stopless
punt and built several arguments on that. It was wrong. A second screenshot shows the SL line
plainly at 4050.00 on a short entered at 4107.38 -- trailed BELOW entry, locking ~57 of the ~80
points then open, with price at 4027 and roughly 22 points (~0.55%) of room left to breathe. In
the principal's words: *"I did have a stop, I kept moving it trying to bank profit while letting
it breathe and run further."*

That is not the absence of discipline this file assumed. It is precisely the trail-and-ride
mechanic implemented below, executed by hand -- and it is a useful DATA POINT on the trail width:
the stop sat roughly 1.9 trail-distances behind price, not the naive 1R the first version of this
ladder used, which is the same direction the measured noise floor pushed the trail. n=1, so it
proves nothing on its own; it is recorded because it agrees with the measurement rather than
because it is impressive.

THE DESIGN PHILOSOPHY, stated plainly because it is the whole point. The desk's edge is NOT being
more cautious per trade than a good discretionary trader -- the screenshot shows one managing risk
properly. It is being able to take the SAME aggressive bet a thousand times, at a size that
survives the losing runs, across more instruments than one person can watch. So:

  AGGRESSION LIVES IN BREADTH AND FREQUENCY, NOT IN BET SIZE, and that is a measured conclusion
  rather than a preference. Simulated over 250 days: at 20% risk per trade this book meets a -90%
  drawdown with near-certainty EVEN WHEN THE STRATEGY IS PROFITABLE, and past full Kelly more size
  makes growth NEGATIVE. Holding total risk fixed at ~24% and changing only its SHAPE, one bet at
  24% gives P(-90%)=100% while eight bets at 3% give P(-90%)=0% with a far higher median. So the
  sleeve runs 18 instruments, hourly, up to five positions at once, 6% each -- MORE total exposure
  than one-bet-at-20% ever ran, spread where it compounds instead of where it ruins. On a 0.9%
  structural stop 6% is still ~6.7x, the screenshot's own range. Timidity is a defect (L1.28);
  so is confusing bet size with aggression.

  RUIN IS CAPPED, and this is the one line that does not move. EVERY position carries a stop,
  per-trade loss is bounded, portfolio leverage is bounded,
  and the whole sleeve sits inside the -35% ruin rail like everything else (L1.23). This is not
  the timid reading of a restraint -- it is the mathematics of compounding: E[log wealth] of a
  ruined book is minus infinity, so the bet that can ruin you is never the growth-optimal bet
  however good it looks (the Alameda row in the desk's own cohort register).

  THE STOP IS CALCULATED, NOT CHOSEN -- which is the ONE thing a hand-managed book cannot do at
  scale, and therefore where the desk's advantage actually lies. A percentage stop is an arbitrary distance the market has
  never heard of; a STRUCTURAL stop sits at the price where the thesis is factually dead -- the
  swing the trend must not lose, the range edge, the level that was defended. This desk refuses
  an asserted `stop_pct`: the model must name an invalidation PRICE and the structure it belongs
  to, and the distance is DERIVED from it. That is not a formality, it is free leverage. Kelly
  sizes `risk_budget / stop_distance`, so a stop that sits 1% away at a real swing carries FOUR
  TIMES the size of a lazy 4% stop at the same risk budget and the same edge -- tighter honest
  invalidation is the single cheapest source of aggression on this desk.

  WINNERS ARE RIDDEN, NOT TAKEN. "Put trades until the trend and swing hits" -- so there is no
  fixed take-profit. The position moves to breakeven at +1R, trails one R behind, and ADDS on
  strength (up to 1.75u, less when the trail is noise-widened) while the trend holds, exiting when price closes back
  through the trailing structure. The pyramid is not extra risk: by the time the first add goes
  on, the original tranche's stop is at breakeven, so OPEN RISK FALLS at every stage
  (1.00 -> 0.50 -> 0.25 -> 0.00 of the initial budget) while exposure RISES. That asymmetry is
  the literal instruction -- minimise downside, maximise upside -- expressed as arithmetic and
  pinned by tests rather than as an intention.

  IT IS SCORED. Every call is a pre-registered forecast (direction, probability, expected move,
  stop) logged to the L1.29 calibration fence. A directional trader who cannot be scored is a
  gambler with a good story; this one finds out whether its conviction is CALIBRATED. If its 70%
  calls win 50% of the time, it is over-confident and the Kelly sizer shrinks automatically.

  PAPER ONLY until it earns real size the same way everything does (L1.6): a forward clock, and
  it must beat buy-and-hold AND the carry sleeve after costs. It places no orders here.

WHY THE STOP ALWAYS HITS BEFORE LIQUIDATION, which is the failure mode that kills leveraged
directional books: sizing solves leverage = risk_fraction / stop_distance, so leverage * stop
distance == risk_fraction <= 0.06 BY CONSTRUCTION, while liquidation sits at roughly 1/leverage.
The stop is therefore never more than ~6% of the way to liquidation at any leverage this sleeve
can produce. It is structurally impossible for this sizer to build a position that gets
liquidated before its stop is touched.

WHAT THE NOTIONAL CEILING IS ACTUALLY FOR, since the above makes liquidation a non-argument: a
cascade printing THROUGH the stop before the fill. That loss scales with NOTIONAL and not with
the planned stop distance, so it is the one exposure a tighter stop does not reduce -- and it is
therefore the only honest reason to cap leverage at all. The cap is consequently DERIVED from
surviving a 2% slip rather than picked as a round number. The flat 10x it replaced was actively
anti-aggression: it made a 0.9% structural stop deploy 9% of the risk budget while a lazy 2% stop
deployed the full 20%, the desk's own ceiling penalising the exact behaviour the calculated stop
exists to produce (L1.28).

ONE THING IS DELIBERATELY WITHHELD FROM THE MODEL: where the sizing optimum sits. Because gap
risk caps the tightest stops, deployed risk peaks around a 1.3-2% invalidation rather than at
zero -- and a model told that would drift toward naming levels that maximise its own size instead
of levels where its thesis is actually dead. That is the same PASS-optimisation failure the event
sleeve had to have designed out of it. The brief asks for the honest level and nothing else; the
sizer's shape is the desk's business, not the trader's.

INSTRUMENTS: 18 liquid Binance perps, plus PAXGUSDT as the on-Binance gold analogue of the
screenshot's XAUUSD -- the one non-crypto-beta name, and so the one position that can be
uncorrelated when everything else moves together.

    python scripts/run_conviction_trader.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/conviction_book.jsonl"
_STATE = "data/conviction_trader.json"

#: THE UNIVERSE. Widened from 4 to 18 because BREADTH IS THE COMPOUNDING LEVER and size is not --
#: see MAX_RISK_PER_TRADE below for the simulation that forced this. Four instruments means the
#: sleeve either takes a mediocre setup or passes; eighteen means it can wait for the good one and
#: still be in the market, which is what a professional discretionary book actually looks like.
#: All verified live on the venue fallback chain 2026-07-31. PAXGUSDT is the on-Binance gold
#: analogue of the principal's XAUUSD screenshot and is deliberately kept: it is the only
#: non-crypto-beta instrument here, so it is the one position that can be uncorrelated with the
#: other seventeen when everything else moves together.
INSTRUMENTS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT", "BNBUSDT", "XRPUSDT",
               "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT",
               "SUIUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "PEPEUSDT", "HYPEUSDT")
MIN_PROB, MAX_PROB = 0.52, 0.90        # below 52% is the other side; 90%+ is an over-confidence tell
#: HALF-Kelly. Full Kelly maximises growth but has an expected drawdown near 50% and is
#: catastrophically sensitive to over-estimating p: betting 1.5x Kelly (what a 35% hit rate would
#: make of a 45% assumption) turns positive growth NEGATIVE. Half-Kelly keeps 75% of the growth
#: rate for 25% of the variance -- the standard result, and the reason the fraction is 0.5 and not
#: 1.0 or 0.25.
KELLY_FRACTION = 0.5
#: 20x. DERIVED, not chosen: it is the gap-stress cap evaluated at the tightest legal stop --
#: 0.50 stress loss / ((0.5% stop + 2% slip)/100) = 20.0x. Above that even the tightest structural
#: stop cannot survive a 2% cascade through it. Replaced a flat 10x that was picked by taste and
#: turned out to penalise tight stops (see MAX_RISK_PER_TRADE for the pattern).
MAX_LEVERAGE = 20.0
#: 0.5% absolute floor, superseded per-instrument by the MEASURED noise floor below (PAXG 24h
#: 0.64%, SOL 24h 1.28% -- measured live 2026-07-31). This constant now only catches the case
#: where the measurement is unavailable; it is a fallback, not the rule.
MIN_STOP_PCT = 0.5
#: 15%. DERIVED from the sizer's own arithmetic: at a 6% risk budget a 15% stop implies 0.4x
#: leverage, at which point the position is no longer a leveraged directional bet and belongs in
#: the spot/carry sleeves instead. Beyond it a "stop" is a hope, not an invalidation.
MAX_STOP_PCT = 15.0

#: THE NOISE FLOOR, and the second flat constant on this desk that turned out to be hiding a
#: defect. MIN_STOP_PCT is a single number applied to gold and to SOL alike -- but a 1% stop is
#: outside the noise on PAXGUSDT and deep inside it on SOLUSDT, so one of those trades is being
#: stopped out by wiggle rather than by being wrong. A stop inside the noise converts a correct
#: thesis into a loss, which is the most expensive way to be right.
#:
#: So the floor is MEASURED per instrument and per horizon: over the last few days of bars, take
#: every rolling window the length of this trade's horizon and record how far price went AGAINST
#: an entry at the window's start. The median of those is the adverse excursion a random entry
#: normally survives. An invalidation closer than that is not an invalidation.
#:
#: FOUND BY MEASUREMENT, not by argument: the first live resolver run marked a PAXGUSDT short
#: whose thesis was correct (gold fell) at -0.13R, because a 1.04% structural stop trailed to
#: breakeven sat inside gold's ordinary retrace.
NOISE_MULT = 1.0                       # the stop must clear the median adverse excursion
NOISE_LOOKBACK_HOURS = 96
#: PER-TRADE RISK, and the single most consequential number in this file. It was 20%, chosen by
#: analogy to a screenshot. Simulating it settled the question rather than arguing it (250
#: sequential days, winners +3R after the trail, losers -1R). No return figure is restated as an
#: objective here -- the desk does not chase a CAGR target (PROJECT_HANDOFF.md 2026-07-12); this
#: is the survival arithmetic that bounds size whatever the ambition:
#:
#:      risk/trade   true hit rate   median year   P(-90% drawdown)
#:            20%             35%        +9064%              96%
#:            20%             30%          -98%             100%
#:             5%             30%          351%               2%
#:
#: At 20% the book meets a -90% drawdown with near-certainty EVEN WHEN THE STRATEGY IS
#: PROFITABLE -- it is wiped out on the way to the gain -- and at a 30% hit rate 20% sits past
#: full Kelly, where more size makes growth NEGATIVE. Meanwhile 5% clears the target several
#: times over. The target never needed bigger bets.
#:
#: This is NOT a retreat from aggression, and the second simulation is the proof. Holding TOTAL
#: heat fixed at ~24% and only changing its shape (35% hit rate):
#:
#:      1 bet @ 24%   median +1058%   5th pct -100%   P(-90%) 100%
#:      4 bets @  6%  median  huge    5th pct  huge   P(-90%)   1%
#:      8 bets @  3%  median  huge    5th pct  huge   P(-90%)   0%
#:
#: Same money at risk, spread across independent instruments: strictly better median AND a
#: near-zero chance of the drawdown that ends the account. So the aggression moved from SIZE to
#: BREADTH and FREQUENCY -- an 18-instrument universe, hourly, several positions live at once.
#: On a 0.9% structural stop 6% still buys ~6.7x leverage, which is the screenshot's own range.
MAX_RISK_PER_TRADE = 0.06              # at most 6% of sleeve equity at risk on one call

#: TOTAL heat across all live positions. This is the real aggression dial now, and at 30% it is
#: HIGHER than the old design ever ran (one 20% bet at a time), while every individual bet is
#: survivable. Enforced against the open book, not assumed.
#: 30% = 5 concurrent positions at the 6% per-trade budget. DERIVED from the shape simulation
#: above: at ~24% total heat, 1 bet gives P(-90%)=100%, 4 bets 1%, 8 bets 0%. Five slots sits in
#: the safe part of that curve while keeping total exposure ABOVE what the old one-bet-at-20%
#: design ever ran.
MAX_PORTFOLIO_HEAT = 0.30

#: HOLD LIMIT vs FORECAST HORIZON -- decoupled, because measuring showed they were fighting.
#: `horizon_hours` is the model's CALIBRATION clock ("when I expect to be right"); it was also
#: being used as a hard exit, which truncates winners for a reason that has nothing to do with the
#: trade. Measured on the marked gold short: the SAME position marks +0.07R at a 12h horizon and
#: +0.63R at 30h. An arbitrary clock was setting the P&L instead of the structure.
#: A trade now runs to its STRUCTURAL exit -- stop or trail -- with 4x its stated horizon as a
#: hard time stop so nothing can sit open forever and escape scoring. 4x is derived from the
#: ladder itself: reaching the last rung needs 3 trail-distances of favourable movement, and a
#: trend that has not managed that in 4x its own forecast horizon is a thesis that did not happen.
MAX_HOLD_MULT = 4.0

#: CORRELATION STRESS. Effective heat uses MEASURED correlations, which is what lets genuine
#: diversification buy real capacity -- measured live 2026-07-31: PAXG vs crypto averages +0.15
#: while crypto-vs-crypto averages +0.48, so a gold position alongside four alts is nothing like
#: a fifth alt. But correlations RISE toward 1 in exactly the cascade that would hurt, and a rail
#: that trusts calm-market correlations is a rail that fails when it matters. So every measured
#: correlation is shrunk 35% of the way toward 1.0 before use: +0.15 becomes +0.45, +0.80 becomes
#: +0.87. Diversification is credited, but only two thirds of it.
CORR_STRESS = 0.35
#: Hard ceiling on the NOMINAL sum regardless of how diversifying the book looks. Correlation
#: estimates can be wrong; 50% caps how wrong they are allowed to make the book. At the 6% budget
#: that is 8 concurrent positions, matching the shape simulation's safest tested point.
MAX_GROSS_HEAT = 0.50

#: THE GAP-RISK STRESS, and the reason there is a notional ceiling at all. The stop being hit is
#: priced: that is MAX_RISK_PER_TRADE and the sizer targets it exactly. What is NOT priced is a
#: cascade printing THROUGH the stop before the fill -- and that loss scales with NOTIONAL, not
#: with the planned stop distance, so it is the one exposure a tight stop does not reduce. The
#: ceiling is therefore derived, not chosen: leverage may go as high as it likes provided a
#: violent 2% slip past the stop still leaves the sleeve alive.
#:
#: This replaced a flat 10x cap that was actively anti-aggression: it made a 0.9% structural stop
#: deploy 9% of the risk budget while a lazy 2% stop deployed the full 20% -- the desk's own
#: ceiling punishing the exact behaviour the calculated stop exists to produce (L1.28).
#: HONEST STATUS AFTER THE RISK RECUT: at a 6% per-trade budget this cap no longer binds anywhere
#: in the legal stop range (0.5-15%) -- the risk budget is the tighter constraint everywhere, so
#: the stress cap is currently INERT. By this desk's own standard a rail that can never fire is
#: decoration, so it is named as one rather than counted as protection. It is kept because it is
#: the thing that must hold if MAX_RISK_PER_TRADE is ever raised again, and a test pins that
#: leverage never exceeds it. Do not read it as active protection today.
SLIP_STRESS_PCT = 2.0                  # a liquidation cascade prints this far through the stop
#: 0.50 -- a 2% cascade through the stop costs at most half the sleeve. Chosen against the
#: drawdown simulation: a 50% hit is survivable and recoverable (needs +100% to restore), whereas
#: the -90% outcomes that the 20% risk budget produced need +900% and never come back.
MAX_STRESS_LOSS = 0.50
#: 0.60, measured as
MAX_PEAK_STRESS_LOSS = 0.60            # drawdown FROM THE STAGE TRIGGER, where the book is up
#: ~0.47 unrealised (computed from the tranche ladder at the +2 rung): so the bound says a cascade
#: may cost the pyramid its own open gains and ~13% more, never the starting stake. Derived as
#:                                       drawdown FROM THE STAGE TRIGGER: by then the position is
#:                                       up roughly that much unrealised, so the bound says the
#:                                       pyramid may give back its own open gains in a cascade --
#:                                       never the starting stake.

#: The pyramid: units added at each rung. Each rung first TRAILS the stop one TRAIL DISTANCE
#: behind, THEN adds -- which is why open risk falls as size grows. Deliberately geometric-
#: decaying: the trend that has already run two rungs has less remaining runway than the one that
#: just started, so the adds get smaller, not larger. Peak exposure 1.75u.
#: (0.50, 0.25) -- geometric halving, giving peak exposure 1.75u. DERIVED from the risk ladder
#: rather than chosen: with each rung trailing one distance behind, these sizes are exactly what
#: makes open risk fall 1.00 -> 0.50 -> 0.25 -> 0.00 of the entry budget while exposure rises, the
#: asymmetry the tests assert. Larger adds break the monotone fall; smaller ones leave upside
#: unclaimed for no risk reduction.
ADD_UNITS: tuple[float, ...] = (0.50, 0.25)

#: THE TRAIL DISTANCE, and the third flat constant that turned out to be a defect. The ladder used
#: to trail exactly 1R behind, which means the breakeven move at +1R leaves the stop one R from
#: price -- and since the entry stop is allowed to sit AT the noise floor, that trailed stop sits
#: at the noise floor too. It has to pass the same test the entry stop passes, and it did not.
#:
#: So the trail is max(1R, 1.5x the measured noise), and the rungs are spaced one trail distance
#: apart so each rung's stop lands exactly where the previous rung triggered. When the noise floor
#: is not binding this reduces EXACTLY to the old 1R ladder; it only ever gives the trade room it
#: measurably needs. That is a GENERALISATION of the old rule, not a different design.
#:
#: EVIDENCE STATUS, stated plainly because the temptation is to imply otherwise: this change is
#: derived from a principle (every stop in the ladder passes the same noise test), NOT fitted to
#: an outcome, and on the one trade marked so far it did not help -- the 1.5%-stop variant went
#: from -0.19R to -0.22R. n=1 in both directions is nothing. It is kept because it is consistent
#: and reduces to the prior behaviour when noise is not binding, and it stays on the forward clock
#: like everything else. Do not read it as a fix that has been shown to work.
#:
#: What that same marking DID establish is separate and larger: at every stop width where the
#: trade survived (2%+), it was still OPEN at a positive R when the 30h horizon expired. The
#: binding constraint on that trade was the HORIZON, not the stop and not the trail.
NOISE_TRAIL_MULT = 1.5

#: A stop is only "calculated" if it sits at something the market drew. This vocabulary is how the
#: fence tells a structural level from a number someone liked. Kept broad on purpose -- a false
#: refusal here costs a real trade, and the binding checks are the price ones below.
_STRUCTURE_WORDS = (
    "swing", "range", "high", "low", "support", "resistance", "breakout", "breakdown",
    "consolidation", "pivot", "shelf", "level", "trendline", "trend line", "channel", "gap",
    "vwap", "liquidity", "order block", "session", "prior day", "prior week", "prior session",
    "base", "neckline", "wick", "close", "open interest", "poc", "value area", "fib", "band",
)

#: MINIMUM MEANINGFUL SIZE. Not an EV bound -- cost scales with notional, so cost/risk is constant
#: and a small trade is proportionally as good as a large one. This is the VENUE minimum: Binance
#: USD-M rejects orders under ~$5 notional, and at a $200 sleeve a 0.1% risk on a 2% stop is $10
#: of notional. Below this the order simply will not fill, so booking it would be fiction.
MIN_TRADE_RISK = 0.001

#: SLEEVE DRAWDOWN HALT. Per-trade risk is bounded; a LOSING RUN is not. At a 20% budget three
#: stops in a row is -49% of the sleeve, which is why a sleeve-level rail has to exist before real
#: money does rather than after the first bad week. Read from the resolver's marked equity curve
#: (R0133) -- which also means this rail is only as alive as the marking is, so an unmarked book
#: reports NO-HISTORY and never OK (L1.28a).
SLEEVE_DD_HALT = 0.35                  # same shape as the book's -35% ruin rail (L1.23)
_PNL_STATE = "data/paper_book_pnl.json"

#: How far the model's own asserted stop_pct may disagree with the level it named before the call
#: is refused as internally inconsistent. A model that names a swing 1% away and then writes
#: "stop_pct: 3" did not reason about the level; it decorated a number.
STOP_MISMATCH_TOL = 0.25               # relative


def slip_leverage_cap(stop_pct: float, *, stress_loss: float = MAX_STRESS_LOSS) -> float:
    """The only honest reason to cap notional: a cascade that prints THROUGH the stop costs
    leverage * (stop + slip), and the slip term does not shrink when the stop tightens. So the
    ceiling is derived from survival under that stress rather than picked as a round number --
    which is what lets a genuinely tight structural stop buy the size it has earned."""
    return stress_loss / ((stop_pct + SLIP_STRESS_PCT) / 100.0)


def kelly_leverage(prob: float, reward_risk: float, stop_pct: float) -> dict[str, Any]:
    """Fractional-Kelly leverage from Claude's OWN probability. Aggression is here; the caps are
    the rail. Kelly f* = (p*b - q)/b; leverage = (fraction of equity at risk) / (stop distance).

    `risk_fraction` is what the position ACTUALLY loses at its stop, not what Kelly asked for.
    Those differ whenever MAX_LEVERAGE binds -- a 0.9% structural stop wants 22x, gets 10x, and
    therefore risks 9% of equity, not the 20% Kelly requested. Reporting the request as though it
    were the exposure would overstate downside everywhere it is consumed (the whole management
    ladder is denominated in it), so the realised number is the one that carries the name."""
    p, q, b = prob, 1.0 - prob, max(reward_risk, 1e-6)
    edge = (p * b - q) / b                                  # full-Kelly fraction of equity
    want = max(0.0, edge * KELLY_FRACTION)                  # half-Kelly, before any cap
    budget = min(MAX_RISK_PER_TRADE, want)
    if stop_pct <= 0:
        return {"full_kelly": round(edge, 4), "kelly_risk_fraction": round(budget, 4),
                "risk_fraction": 0.0, "leverage": 0.0, "slip_cap": 0.0, "capped_by": "no-stop"}
    kelly_lev = budget / (stop_pct / 100.0)
    slip_cap = slip_leverage_cap(stop_pct)
    lev = min(MAX_LEVERAGE, slip_cap, kelly_lev)
    realised = lev * (stop_pct / 100.0)                     # what the stop actually costs
    caps = []
    if want > MAX_RISK_PER_TRADE:
        caps.append("max_risk")
    if slip_cap < min(kelly_lev, MAX_LEVERAGE):
        caps.append("gap_stress")
    if MAX_LEVERAGE < min(kelly_lev, slip_cap):
        caps.append("max_leverage")
    return {"full_kelly": round(edge, 4), "kelly_risk_fraction": round(budget, 4),
            "risk_fraction": round(realised, 4), "leverage": round(lev, 2),
            "slip_cap": round(slip_cap, 2),
            "capped_by": "no-edge" if edge <= 0 else ("+".join(caps) if caps else "kelly")}


def derive_stop_pct(entry_ref: float, invalidation: float, direction: str) -> tuple[float, str]:
    """THE CALCULATED STOP. Distance is derived from the named invalidation level, never asserted.

    Returns (stop_pct, "") or (0.0, refusal). An invalidation on the wrong side of entry is the
    tell that the model produced a level to satisfy the schema rather than to mark where its
    thesis dies -- that is a target, not a stop, and it is refused."""
    if not (entry_ref > 0 and invalidation > 0):
        return 0.0, "REFUSED: entry_ref and invalidation must both be positive prices"
    if direction == "LONG" and invalidation >= entry_ref:
        return 0.0, (f"REFUSED: a LONG's invalidation ({invalidation}) must sit BELOW entry "
                     f"({entry_ref}) -- a level above entry is a target, not a stop")
    if direction == "SHORT" and invalidation <= entry_ref:
        return 0.0, (f"REFUSED: a SHORT's invalidation ({invalidation}) must sit ABOVE entry "
                     f"({entry_ref}) -- a level below entry is a target, not a stop")
    return abs(entry_ref - invalidation) / entry_ref * 100.0, ""


def management_plan(entry: float, invalidation: float, direction: str, *,
                    risk_fraction: float, leverage: float,
                    noise_pct: float | None = None) -> dict[str, Any]:
    """"PUT TRADES UNTIL THE TREND AND SWING HITS" -- the trail-and-pyramid ladder, computed.

    Every stage's open risk and locked profit are COMPUTED from the tranche book, not asserted, so
    the asymmetry the principal asked for is arithmetic a test can check: exposure rises
    1.00u -> 1.50u -> 1.75u while open risk falls 1.00 -> 0.50 -> 0.25 -> 0.00 of the initial
    budget. There is no take-profit anywhere in here on purpose: the exit is the structure
    breaking, which is what lets one trend pay for the losers."""
    sign = 1.0 if direction == "LONG" else -1.0
    r = abs(entry - invalidation)                            # 1R, in price
    if r <= 0:
        return {"status": "UNPLANNABLE", "why": "zero-width R -- entry equals invalidation"}
    stop_pct = r / entry * 100.0

    # THE TRAIL must clear the noise for the same reason the entry stop must: a stop inside the
    # wiggle exits a correct thesis. Rungs are spaced one trail distance apart so each rung's stop
    # lands exactly where the previous rung triggered -- with no noise floor this is the old 1R
    # ladder unchanged.
    trail = r if noise_pct is None else max(r, NOISE_TRAIL_MULT * (noise_pct / 100.0) * entry)

    # The pyramid gets the same gap-stress test as the entry, at the looser peak bound: the adds
    # only ever go on once the earlier tranches are stopped at or above breakeven, so a cascade
    # through the trail hits size that is no longer risking the entry budget. If the full ladder
    # would breach it, the ADDS shrink -- never the rail.
    peak_cap = min(MAX_LEVERAGE, slip_leverage_cap(stop_pct, stress_loss=MAX_PEAK_STRESS_LOSS))
    raw_peak_units = 1.0 + sum(ADD_UNITS)
    add_scale = 1.0
    if leverage > 0 and leverage * raw_peak_units > peak_cap:
        add_scale = max(0.0, min(1.0, (peak_cap / leverage - 1.0) / (raw_peak_units - 1.0)))

    def at(mult: float) -> float:                            # price at +mult R in the trade's favour
        return entry + sign * r * mult

    def rung(k: float) -> float:                             # price k trail-distances in favour
        return entry + sign * trail * k

    tranches: list[tuple[float, float]] = [(entry, 1.0)]     # (entry price, units)

    def book(stop: float) -> tuple[float, float]:
        """Open risk and locked profit at a given stop, as fractions of the initial risk budget."""
        risk = sum(u * risk_fraction * max(0.0, (e - stop) * sign) / r for e, u in tranches)
        locked = sum(u * risk_fraction * max(0.0, (stop - e) * sign) / r for e, u in tranches)
        return round(risk, 4), round(locked, 4)

    orisk, olock = book(invalidation)
    stages: list[dict[str, Any]] = [{
        "at_R": 0.0, "trigger": round(entry, 8), "stop": round(invalidation, 8),
        "action": "ENTER 1.00u at the level; stop at the named invalidation",
        "units": 1.0, "notional_leverage": round(leverage, 2),
        "open_risk_frac": orisk, "locked_profit_frac": olock}]

    for k, add_raw in enumerate(ADD_UNITS, start=1):
        # THE ADD IS SIZED BY RISK, NOT BY UNITS. Its stop sits one TRAIL behind it, so at a
        # noise-widened trail each unit added carries trail/R of risk rather than 1R. Adding a
        # flat 0.50u there would make open risk RISE at the first rung -- caught by the invariant
        # test, which is the whole reason that test asserts on computed numbers.
        add_u = round(add_raw * add_scale * (r / trail), 4)
        stop = rung(k - 1)                                   # trail ONE trail-distance behind
        tranches.append((rung(k), add_u))
        units = sum(u for _, u in tranches)
        orisk, olock = book(stop)
        where = "breakeven" if k == 1 else f"the +{k - 1} rung"
        stages.append({
            "at_R": round(trail * k / r, 3), "trigger": round(rung(k), 8), "stop": round(stop, 8),
            "action": f"TRAIL stop to {where}, THEN ADD {add_u:.2f}u (risk falls as size grows)",
            "units": round(units, 2), "notional_leverage": round(leverage * units, 2),
            "open_risk_frac": orisk, "locked_profit_frac": olock})

    final_k = len(ADD_UNITS) + 1
    stop = rung(final_k - 1)
    orisk, olock = book(stop)
    units = sum(u for _, u in tranches)
    stages.append({
        "at_R": round(trail * final_k / r, 3), "trigger": round(rung(final_k), 8),
        "stop": round(stop, 8),
        "action": "TRAIL behind each new swing as it forms; NO further adds, NO fixed target -- "
                  "hold until price closes back through the trailing structure",
        "units": round(units, 2), "notional_leverage": round(leverage * units, 2),
        "open_risk_frac": orisk, "locked_profit_frac": olock})

    peak = max(s["notional_leverage"] for s in stages)
    return {
        "status": "OK" if add_scale >= 1.0 else "PYRAMID-SCALED",
        "r_price": round(r, 8), "stop_pct": round(stop_pct, 4),
        "trail_price": round(trail, 8), "trail_R": round(trail / r, 3),
        "trail_source": "noise-widened" if trail > r * 1.000001 else "1R (noise not binding)",
        "peak_units": round(units, 2), "peak_leverage": round(peak, 2),
        "peak_leverage_cap": round(peak_cap, 2), "add_scale": round(add_scale, 4),
        "peak_stress_loss": round(peak * (stop_pct + SLIP_STRESS_PCT) / 100.0, 4),
        "stages": stages,
        "exit_rule": "structure break only -- price closing back through the trailing swing. No "
                     "take-profit: capping the winner is what makes a stopped-out book "
                     "negative-EV even with a real edge.",
        "invariant": "open_risk_frac is non-increasing across stages and never exceeds the "
                     "initial risk budget; locked_profit_frac is non-decreasing.",
    }


_BRIEF = """You are the desk's CONVICTION TRADER. You take AGGRESSIVE leveraged DIRECTIONAL bets --
this is the sleeve modelled on a sharp manual trader flipping an account fast, not the cautious
news reader. You are ENCOURAGED to size up when you have real conviction. You carry a CALCULATED
STOP on every trade and you will be SCORED, so your confidence must be honest.

INSTRUMENTS: {instruments}. Take a directional view -- macro, technical, flow, positioning,
cross-asset (gold via PAXGUSDT, risk via BTC/ETH). A VIEW is allowed here (unlike the event
sleeve), but state the DRIVER: what makes this move happen, and what would kill it.

YOUR CHARTS -- multi-timeframe structure for every instrument: swing highs and lows with TOUCH
COUNTS (a level defended three times is not the level touched once), trend state read from the
swing sequence, position in range, distance to the nearest level each way, and volatility regime.
Read them like a trader: is the 4h trend with you, is there room to the next level, is the
invalidation you want to use an actual defended structure or a random pivot?
{charts}

THE DESK'S OWN PLAYBOOK -- lessons this sleeve LEARNED from its own closed Binance trades, each
one held to {n_support}+ independent agreeing trades before it was allowed to reach you, and
retired the moment a trade contradicted it. These are not platitudes; they are this desk's
measured experience. Weigh them against what you see, and if the chart contradicts one, SAY SO in
your reasoning -- a lesson that stops matching reality needs to be retired, and you are the only
thing that can notice.
{playbook}

PICK THE BEST SETUP IN THE UNIVERSE, not the first readable one. You get one call per hour across
18 instruments and several positions can be live at once, so a mediocre setup costs you the good
one you would otherwise have had heat for. The right answer is often PASS.

THE STOP IS A LEVEL, NOT A PERCENTAGE. Name the PRICE at which your thesis is factually dead --
the swing the trend must not lose, the range edge, the shelf that was defended -- and name the
structure it is. The desk DERIVES the stop distance from that level; it will refuse an
invalidation on the wrong side of entry, and refuse a stop that is not at a named structure.
THIS IS WHERE YOUR SIZE COMES FROM: the desk sizes risk_budget / stop_distance, so a stop 1% away
at a real swing carries FOUR TIMES the size of a lazy 4% stop on the same edge. Find the tightest
HONEST invalidation, not a comfortable one -- and not one so tight that noise takes you out.

THE NOISE FLOOR IS MEASURED, PER INSTRUMENT AND PER HORIZON: {noise}
A level closer than that gets hit by ordinary wiggle rather than by your thesis failing, and the
desk refuses it. If your level is inside the floor, either name a level further out or ask for a
SHORTER horizon -- a short horizon has a smaller floor, which is how a tight level stays legal.

YOUR WINNERS ARE RIDDEN, NOT TAKEN. There is no take-profit. The desk moves your stop to
breakeven at +1R, trails one R behind, and ADDS on strength (1.00u -> 1.50u -> 1.75u) while the
trend holds, exiting only when price closes back through the trailing structure. So do NOT pick a
small nearby target: expected_move_pct is your estimate of the move if you are right, and the
trade is held until the structure breaks, not until that number prints.

TODAY'S BRIEF (numeric context; you may reason over it, the desk's pipelines handle the arithmetic):
{brief}

OUTPUT EXACTLY ONE JSON OBJECT:
{{"action": "TRADE" | "PASS",
  "symbol": "one of the instruments",
  "direction": "LONG" | "SHORT",
  "probability": 0.63,             // YOUR honest P(this trade is profitable). SCORED against outcome.
  "entry_ref": 4107.4,             // the price you are entering at (current or your trigger)
  "invalidation": 4190.0,          // the PRICE where the thesis is dead. Below entry if LONG, above if SHORT.
  "structure": "the prior-session swing high that capped the last two attempts",
  "expected_move_pct": 4.0,        // the move you expect if right, percent -- not a take-profit
  "horizon_hours": 12,
  "driver": "what forces/drives this move",
  "falsifier": "the observation that kills the thesis before the stop",
  "reasoning": "2-4 sentences"}}

BE AGGRESSIVE ON CONVICTION, HONEST ON PROBABILITY. The desk sizes the trade FOR you by
fractional-Kelly against your probability and your derived stop -- a 0.63 with a 2% structural
stop becomes real leverage automatically, so you do not need to inflate confidence to get size;
inflating it only makes the calibration fence catch you and SHRINK your future size. reward:risk
= expected_move_pct / derived stop must exceed 1.2 or the trade is refused (you are risking more
than you stand to make). Derived stop must land between {smin}% and {smax}%. PASS with a reason
if there is no directional edge -- but a conviction trader that always passes is not doing its
job. Probability must be {lo}-{hi}."""


def adverse_excursion(bars: list[tuple[int, float, float, float, float]], horizon_hours: float,
                      direction: str) -> float | None:
    """Median adverse excursion over rolling windows of this trade's own horizon, in percent.

    "How far does price normally go against me before the horizon is up?" -- computed from the
    instrument's own bars rather than assumed. Returns None when there are not enough bars, which
    the caller must surface as UNMEASURED rather than treat as zero noise."""
    w = max(1, int(round(horizon_hours * 4)))                # 15m bars
    if len(bars) < w + 8:
        return None
    sign = 1.0 if direction == "LONG" else -1.0
    excursions = []
    for i in range(len(bars) - w):
        ref = bars[i][1]                                     # window's open
        if ref <= 0:
            continue
        window = bars[i:i + w + 1]
        worst = (min(b[3] for b in window) if sign > 0 else max(b[2] for b in window))
        excursions.append((ref - worst) * sign / ref * 100.0)
    if not excursions:
        return None
    excursions.sort()
    n = len(excursions)
    return excursions[n // 2] if n % 2 else (excursions[n // 2 - 1] + excursions[n // 2]) / 2


def noise_floor(symbol: str, horizon_hours: float, direction: str, *,
                fetch=None) -> dict[str, Any]:
    """The per-instrument minimum honest stop. UNMEASURED falls back to the flat floor and SAYS
    SO -- a silent fallback would restore exactly the defect this replaced."""
    if fetch is None:
        try:
            from scripts.resolve_paper_book import fetch_bars as fetch
        except ImportError as exc:
            return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                    "why": f"price source unavailable ({exc}); flat floor in use"}
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    span = int((NOISE_LOOKBACK_HOURS + horizon_hours) * 3600 * 1000)
    bars, source = fetch(symbol, now_ms - span, now_ms)
    if not bars:
        return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                "why": f"no bars for {symbol} ({source}); flat floor in use -- the noise check "
                       "did NOT pass, it did not run"}
    med = adverse_excursion(bars, horizon_hours, direction)
    if med is None:
        return {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT,
                "why": f"only {len(bars)} bars, too few for a {horizon_hours}h window"}
    floor = max(MIN_STOP_PCT, NOISE_MULT * med)
    return {"state": "MEASURED", "floor_pct": round(floor, 4), "median_adverse_pct": round(med, 4),
            "bars": len(bars), "source": source,
            "why": f"a random {horizon_hours}h entry in {symbol} normally goes {med:.2f}% against "
                   f"itself; an invalidation closer than that is noise, not a thesis failing"}


def noise_table(*, horizons: tuple[float, ...] = (8.0, 24.0, 48.0), fetch=None) -> dict[str, Any]:
    """The floor for every instrument and horizon, published INTO the brief.

    Withholding it would refuse the model's level without ever telling it the rule, which is how a
    gate becomes noise the caller learns to route around. Note what is published and what is not:
    the noise floor is a CONSTRAINT the model must satisfy, so it gets it; where the sizing optimum
    sits is a REWARD it could chase, so it does not."""
    if fetch is None:
        try:
            from scripts.resolve_paper_book import fetch_bars as fetch
        except ImportError as exc:
            return {"state": "UNMEASURED", "why": f"price source unavailable ({exc})"}
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    span = int((NOISE_LOOKBACK_HOURS + max(horizons)) * 3600 * 1000)
    out: dict[str, Any] = {}
    for sym in INSTRUMENTS:
        bars, source = fetch(sym, now_ms - span, now_ms)
        if not bars:
            out[sym] = f"UNMEASURED ({source}) -- flat {MIN_STOP_PCT}% floor applies"
            continue
        row = {}
        for h in horizons:
            lo = adverse_excursion(bars, h, "LONG")
            sh = adverse_excursion(bars, h, "SHORT")
            row[f"{h:g}h"] = {"LONG": None if lo is None else round(max(MIN_STOP_PCT, lo), 2),
                              "SHORT": None if sh is None else round(max(MIN_STOP_PCT, sh), 2)}
        out[sym] = row
    return {"state": "MEASURED", "min_stop_pct_by_symbol_and_horizon": out,
            "meaning": "the median distance price goes AGAINST a random entry over that horizon; "
                       "an invalidation closer than this is refused as noise"}


def _closed_keys(root: Path) -> set[str]:
    """Trades the resolver has already marked out. Without this a stopped position would keep
    occupying heat until its hard-exit clock ran down -- blocking new trades with capital that
    was returned hours ago, which is idle capacity dressed as prudence (L1.28a)."""
    try:
        rep = json.loads((root / _PNL_STATE).read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return {m.get("key") for m in rep.get("marks", [])
            if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED", "TIME-STOPPED")}


def open_positions(root: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Positions still live: past neither their structural exit nor their hard time stop."""
    now = now or datetime.now(tz=UTC)
    closed_keys = _closed_keys(root)
    live = []
    try:
        lines = (root / _BOOK).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        try:
            # a position occupies heat until its HARD exit, not until its forecast is scored
            until = r.get("hard_exit_by") or r.get("resolve_by")
            if datetime.fromisoformat(until) > now and r.get("action") != "PASS":
                live.append(r)
        except (KeyError, ValueError, TypeError):
            continue
    if closed_keys:
        live = [r for r in live if r.get("at") not in closed_keys]
    return live


def effective_heat(root: Path, live: list[dict[str, Any]]) -> tuple[float, str]:
    """Portfolio risk with MEASURED correlations: sqrt(w' S w), not the naive sum.

    The naive sum is right only if every position is the same trade. It is wrong in BOTH
    directions and both cost money: it overstates safety when five alts are really one bet, and it
    blocks a genuinely diversifying trade (gold beside crypto) that added almost no portfolio
    risk. UNMEASURED correlations fall back to the naive sum and SAY SO -- never to an optimistic
    default, which would let a blind book believe it was diversified."""
    ws = [(r.get("symbol"), float((r.get("sizing") or {}).get("risk_fraction") or 0.0))
          for r in live]
    naive = sum(w for _, w in ws)
    if len(ws) < 2:
        return naive, "single position -- correlation irrelevant"
    try:
        corr = json.loads((root / "data/chart_context.json").read_text("utf-8"))["correlations"]
    except (OSError, ValueError, KeyError):
        return naive, "UNMEASURED correlations -- naive sum used (no diversification credit)"
    var = 0.0
    for a, wa in ws:
        for b, wb in ws:
            rho = 1.0 if a == b else corr.get(a, {}).get(b)
            if rho is None:
                return naive, f"no measured correlation for {a}/{b} -- naive sum used"
            rho = rho + (1.0 - rho) * CORR_STRESS          # stress toward 1, never toward 0
            var += wa * wb * rho
    return var ** 0.5, f"measured correlations, stressed {CORR_STRESS:.0%} toward 1"


def portfolio_heat(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Total risk live across the book, and the rail that makes frequency safe rather than reckless.

    Breadth only beats concentration if the bets are actually SEPARATE. Eight positions all long
    crypto beta in a correlated tape is one position wearing eight names, and the simulation that
    justified widening the universe assumed independence -- so the same-direction concentration is
    reported here rather than quietly ignored. This rail is what allows the cadence to rise: more
    shots at a bounded total exposure is the whole design."""
    live = open_positions(root, now=now)
    gross = sum(float((r.get("sizing") or {}).get("risk_fraction") or 0.0) for r in live)
    longs = sum(1 for r in live if r.get("direction") == "LONG")
    eff, basis = effective_heat(root, live)
    full = eff >= MAX_PORTFOLIO_HEAT or gross >= MAX_GROSS_HEAT
    return {
        "n_open": len(live), "heat": round(eff, 4), "gross_heat": round(gross, 4),
        "cap": MAX_PORTFOLIO_HEAT, "gross_cap": MAX_GROSS_HEAT, "correlation_basis": basis,
        "headroom": round(max(0.0, MAX_PORTFOLIO_HEAT - eff), 4),
        "symbols": [r.get("symbol") for r in live],
        "directional_skew": (f"{longs}L/{len(live) - longs}S" if live else "flat"),
        "state": "FULL" if full else "OPEN",
        "why": (f"{eff:.1%} effective of {MAX_PORTFOLIO_HEAT:.0%} ({gross:.1%} gross of "
                f"{MAX_GROSS_HEAT:.0%}) across {len(live)} positions [{basis}]"
                if live else "no live positions -- full heat available"),
    }


def size_into_headroom(root: Path, symbol: str, desired_risk: float,
                       live: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The heat cap as a SIZER, not a gate -- and the correlation-aware growth lever.

    Refusing a good setup because the book is 95% full throws the setup away; taking it at 5% size
    does not. Idle capacity is unbooked loss (L1.28a), and a slot left empty contributes exactly
    zero to geometric growth while a small position contributes a small positive amount.

    It is also where correlation pays. The largest size that fits is solved against EFFECTIVE heat,
    so a trade uncorrelated with the book (gold beside four alts, measured +0.15) gets far more
    room than one duplicating it (+0.80) -- which is the multivariate-Kelly intuition made
    operational: allocate to the bet that adds the most growth per unit of portfolio risk."""
    live = open_positions(root) if live is None else live
    gross_used = sum(float((r.get("sizing") or {}).get("risk_fraction") or 0.0) for r in live)
    gross_room = max(0.0, MAX_GROSS_HEAT - gross_used)
    if gross_room <= 0:
        return {"risk": 0.0, "bound": "gross_heat", "why": "gross heat cap reached"}

    def fits(w: float) -> bool:
        cand = [*live, {"symbol": symbol, "sizing": {"risk_fraction": w}}]
        return effective_heat(root, cand)[0] <= MAX_PORTFOLIO_HEAT

    hi = min(desired_risk, gross_room)
    if hi <= 0:
        return {"risk": 0.0, "bound": "no room", "why": "no headroom at any size"}
    if fits(hi):
        return {"risk": round(hi, 6),
                "bound": "kelly" if hi >= desired_risk else "gross_heat",
                "why": f"full requested size fits ({len(live)} live)"}
    lo = 0.0
    for _ in range(24):                                    # bisection: effective heat is monotone
        mid = (lo + hi) / 2
        if fits(mid):
            lo = mid
        else:
            hi = mid
    return {"risk": round(lo, 6), "bound": "effective_heat",
            "why": (f"trimmed from {desired_risk:.2%} to {lo:.2%} to stay inside "
                    f"{MAX_PORTFOLIO_HEAT:.0%} effective heat against {len(live)} live "
                    "position(s) -- correlation with the book decides how much fits")}


def sleeve_drawdown(root: Path) -> dict[str, Any]:
    """The sleeve's own drawdown rail, read from the marked paper book (R0133).

    UNMEASURED must never read as OK: an unmarked or unreadable book returns NO-HISTORY, which is
    reported everywhere it is consumed rather than quietly treated as a clean slate."""
    try:
        rep = json.loads((root / _PNL_STATE).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"state": "NO-HISTORY", "halted": False,
                "why": f"paper book not marked on this host ({type(exc).__name__}) -- the "
                       "drawdown rail is BLIND until resolve_paper_book.py has run"}
    eq = rep.get("equity") or {}
    n = int(eq.get("n") or 0)
    if n == 0:
        return {"state": "NO-HISTORY", "halted": False,
                "why": f"book marked but 0 closed calls ({rep.get('status')}) -- rail BLIND"}
    dd = float(eq.get("current_drawdown") or 0.0)
    return {"state": "HALTED" if dd >= SLEEVE_DD_HALT else "OK", "halted": dd >= SLEEVE_DD_HALT,
            "current_drawdown": dd, "max_drawdown": eq.get("max_drawdown"), "n_closed": n,
            "why": (f"sleeve is {dd:.1%} below its high-water mark, at or past the "
                    f"{SLEEVE_DD_HALT:.0%} halt" if dd >= SLEEVE_DD_HALT
                    else f"{dd:.1%} drawdown over {n} closed calls, inside the "
                         f"{SLEEVE_DD_HALT:.0%} rail")}


def _playbook_brief(root: Path) -> str:
    """SUPPORTED lessons only. A single lucky trade must not be able to rewrite the method, so the
    PROVISIONAL tier is deliberately invisible here (see run_trade_review.py)."""
    try:
        pb = json.loads((root / "data/trading_playbook.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ("(no playbook yet -- the review loop has not closed enough trades to support a "
                "lesson. You are trading on general reasoning alone, which is the honest state, "
                "not a clean slate.)")
    live = [lv for lv in pb.get("lessons", []) if lv.get("status") == "SUPPORTED"]
    if not live:
        prov = sum(1 for lv in pb.get("lessons", []) if lv.get("status") == "PROVISIONAL")
        return (f"(no SUPPORTED lessons yet; {prov} provisional and deliberately withheld until "
                f"{N_SUPPORT}+ trades agree. Trade on your own read.)")
    live.sort(key=lambda lv: (-lv.get("support", 0), -lv.get("last_seen_at_trade", 0)))
    return json.dumps([{"lesson": lv["text"], "when": lv.get("applies_when", ""),
                        "evidence": f"{lv.get('support')} agreeing trades"}
                       for lv in live[:12]], indent=1)


def setup_features(call: dict[str, Any], charts: dict[str, Any] | None) -> dict[str, Any]:
    """Tag the SITUATION a trade was taken in, so the desk can learn WHICH SETUPS PAY rather than
    only whether it is globally calibrated.

    A single hit rate over all trades hides everything actionable: a sleeve that is 55% with the 4h
    trend and 25% against it looks like a mediocre 40% overall, and the fix -- stop taking
    counter-trend setups -- is invisible until the outcomes are conditioned on the setup."""
    f: dict[str, Any] = {"symbol": call.get("symbol"), "direction": call.get("direction")}
    tf = ((charts or {}).get("charts", {}).get(str(call.get("symbol")), {})
          .get("timeframes", {}).get("4h", {}))
    trend = str(tf.get("trend", "UNKNOWN"))
    f["trend_4h"] = trend.split(" ")[0]
    f["with_4h_trend"] = (("UPTREND" in trend and call.get("direction") == "LONG")
                          or ("DOWNTREND" in trend and call.get("direction") == "SHORT")
                          if "TREND" in trend else None)
    f["vol_regime"] = tf.get("vol_regime", "UNKNOWN")
    pir = tf.get("position_in_range")
    f["position_in_range"] = (None if pir is None else
                              "low" if pir < 0.33 else "high" if pir > 0.67 else "mid")
    struct = str(call.get("structure", "")).lower()
    f["level_touches"] = next((int(n) for n in re.findall(r"(\d+)[ -]?touch", struct)), None)
    try:
        f["horizon_bucket"] = ("short" if float(call.get("horizon_hours", 0)) <= 12 else
                               "medium" if float(call.get("horizon_hours", 0)) <= 36 else "long")
    except (TypeError, ValueError):
        f["horizon_bucket"] = None
    return f


def _chart_brief(root: Path, heat: dict[str, Any] | None = None, *, max_chars: int = 9000) -> str:
    """The charts, trimmed to what fits and honest about what did not.

    Instruments already live are dropped: heat is capped and the same-symbol trade is refused
    anyway, so spending brief on them buys nothing. STALE and MISSING are stated -- a trader
    reasoning over yesterday's structure while believing it is today's is worse than one who
    knows it is blind."""
    try:
        raw = json.loads((root / "data/chart_context.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return (f"CHARTS UNAVAILABLE ({type(exc).__name__}) -- build_chart_context.py has not run "
                "on this host. You are trading BLIND on structure: do not name a swing level you "
                "cannot see, and PASS unless the non-chart evidence alone is compelling.")
    try:
        age_h: float | None = (datetime.now(tz=UTC)
                               - datetime.fromisoformat(raw["generated"])).total_seconds() / 3600.0
        age_note = f"{age_h:.1f}h old"
    except (KeyError, ValueError) as exc:
        # NOT swallowed: an unreadable timestamp means the trader cannot tell fresh structure from
        # a stale snapshot, and that must reach the trader rather than vanish into a default.
        age_h, age_note = None, f"age UNMEASURED ({type(exc).__name__}) -- treat as possibly STALE"
    held = set((heat or {}).get("symbols") or [])
    charts = {k: v for k, v in (raw.get("charts") or {}).items() if k not in held}
    head = f"(chart context {age_note}, {raw.get('status')}: {raw.get('detail')})\n"
    if age_h is None or age_h > 2:
        head = ("WARNING -- CHART STRUCTURE MAY BE STALE"
                + (f" ({age_h:.1f}h old)" if age_h is not None else "")
                + ", treat levels as approximate.\n") + head
    body = json.dumps(charts, separators=(",", ":"))
    if len(body) > max_chars:
        body = body[:max_chars] + f'... [TRUNCATED at {max_chars} chars of {len(body)}]'
    return head + body


def build_brief(root: Path) -> dict[str, Any]:
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "context": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 4),
                          ("liquidations", "data/liquidations.jsonl", 6),
                          ("tradeable_events", "data/exchange_announcements.jsonl", 6)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "tradeable_events":
                rows = []
                for ln in reversed(lines):
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r.get(k) for k in ("title", "symbols", "tier")})
                    if len(rows) >= n:
                        break
                brief["context"][label] = rows or "none this window"
            else:
                brief["context"][label] = [ln[:300] for ln in lines[-n:] if ln.strip()] or "ABSENT"
        except OSError:
            brief["context"][label] = "ABSENT on this host"
    return brief


def validate(call: dict[str, Any], *, noise: dict[str, Any] | None = None,
             heat: dict[str, Any] | None = None) -> tuple[bool, str]:
    if call.get("action") == "PASS":
        if not call.get("pass_reason"):
            return False, "REFUSED: a PASS must state why -- an unjustified pass is not a decision"
        return True, f"PASS: {str(call['pass_reason'])[:80]}"
    for f in ("symbol", "direction", "probability", "entry_ref", "invalidation", "structure",
              "expected_move_pct", "horizon_hours", "driver", "falsifier"):
        if call.get(f) in (None, ""):
            return False, f"REFUSED: missing {f}"
    if call["symbol"] not in INSTRUMENTS:
        return False, f"REFUSED: symbol must be one of {INSTRUMENTS}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction LONG or SHORT"
    try:
        p, mv = float(call["probability"]), float(call["expected_move_pct"])
        entry, inval = float(call["entry_ref"]), float(call["invalidation"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability/move/entry_ref/invalidation not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB}"

    structure = str(call["structure"]).lower()
    if not any(w in structure for w in _STRUCTURE_WORDS):
        return False, ("REFUSED: the stop must sit at a NAMED market structure (swing, range edge, "
                       "shelf, prior-session level...) -- an arbitrary distance is a number the "
                       "market has never heard of, and it throws away the size a real level buys")
    stop, why = derive_stop_pct(entry, inval, call["direction"])
    if why:
        return False, why
    if not MIN_STOP_PCT <= stop <= MAX_STOP_PCT:
        # A trade with no stop, or a stop so wide it is not a stop, is the one that ends the
        # account. This is not timidity -- it is the difference
        # between compounding the aggressive bet and being ruined by it (L1.23). The tight end is
        # the same rail pointed the other way: an invalidation inside the noise is not a thesis
        # being wrong, it is a wick, and it converts a real edge into churn.
        return False, (f"REFUSED: derived stop {stop:.2f}% outside {MIN_STOP_PCT}-{MAX_STOP_PCT} "
                       "-- every conviction trade carries a real structural stop (L1.23)")
    if noise and noise.get("state") == "MEASURED" and stop < float(noise["floor_pct"]):
        # NOT a timid refusal: taking this trade means being stopped out by ordinary wiggle on a
        # thesis that was correct, which is strictly worse than not taking it. The fix is a level
        # further out or a longer horizon, both of which the model may propose next cycle.
        return False, (f"REFUSED: stop {stop:.2f}% sits INSIDE the noise -- "
                       f"{noise.get('median_adverse_pct')}% is the median adverse excursion for a "
                       f"{call['horizon_hours']}h {call['symbol']} entry, so this level gets hit "
                       "by wiggle rather than by the thesis failing")
    claimed = call.get("stop_pct")
    if claimed not in (None, ""):
        try:
            c = float(claimed)
        except (TypeError, ValueError):
            return False, "REFUSED: stop_pct present but not numeric"
        if abs(c - stop) > STOP_MISMATCH_TOL * stop:
            return False, (f"REFUSED: asserted stop_pct {c}% disagrees with the level named "
                           f"({stop:.2f}% from entry) -- the stop was decorated, not calculated")
    if mv / stop < 1.2:
        return False, (f"REFUSED: reward:risk {mv/stop:.2f} < 1.2 -- risking more than the "
                       "expected gain is negative-EV even when the call is right")
    if len(str(call["driver"])) < 20 or len(str(call["falsifier"])) < 15:
        return False, "REFUSED: driver/falsifier too thin"
    if heat:
        # NOT "the book is busy, come back later" -- that would leave a good setup unbooked, and an
        # unbooked setup contributes exactly zero to geometric growth. The heat cap SIZES the trade
        # (size_into_headroom); it only refuses when nothing fillable fits at all.
        fits = heat.get("fits_risk")
        if fits is not None and fits < MIN_TRADE_RISK:
            return False, (f"REFUSED: no fillable size left -- effective heat {heat['heat']:.1%} "
                           f"against the {MAX_PORTFOLIO_HEAT:.0%} cap leaves {fits:.3%}, below the "
                           f"{MIN_TRADE_RISK:.1%} venue minimum. Breadth is the aggression here, "
                           "not stacking.")
        if fits is None and heat.get("state") == "FULL":
            return False, (f"REFUSED: portfolio heat {heat['heat']:.1%} is at the "
                           f"{MAX_PORTFOLIO_HEAT:.0%} cap and per-symbol headroom is UNMEASURED")
        if call["symbol"] in (heat.get("symbols") or []):
            return False, (f"REFUSED: already live in {call['symbol']} -- doubling the same "
                           "instrument is concentration wearing a second name, which is exactly "
                           "what the spread-the-heat design exists to avoid")
    return True, "accepted"


def calibrated_p(raw_p: float) -> dict[str, Any]:
    """SIZE on the desk's MEASURED accuracy, SCORE the model's raw claim.

    This is the closed loop that protects geometric growth, and it is not a safety feature -- it
    is the growth term itself. Kelly is f* = (pb - q)/b: if the sleeve claims 0.63 and truly hits
    0.45, sizing on 0.63 bets ~2x Kelly, where E[log wealth] is NEGATIVE. No amount of edge
    survives systematically over-betting it.

    It runs in BOTH directions, and the upward one is the point as much as the downward: a desk
    measured UNDER-confident gets its probability raised and therefore its size raised. Aggression
    that has been earned is aggression the sizer hands over automatically.

    N-gated inside forecast_calibration: under 5 resolved outcomes it returns the raw value
    unchanged and says so, because a correction from noise is worse than no correction."""
    try:
        from libs.self_improvement.forecast_calibration import calibrated_confidence
        c = calibrated_confidence(raw_p)
    except Exception as exc:                              # noqa: BLE001 -- never lose the call
        return {"raw": raw_p, "used": raw_p, "applied": False,
                "why": f"UNMEASURED calibration ({type(exc).__name__}) -- sizing on the raw claim"}
    return {"raw": c["raw"], "used": c["adjusted"] if c.get("applied") else c["raw"],
            "applied": bool(c.get("applied")), "bias": c.get("bias"),
            "direction": ("shrunk -- desk measured over-confident" if (c.get("bias") or 0) > 0
                          else "raised -- desk measured UNDER-confident, earned size returned"
                          if (c.get("bias") or 0) < 0 else "unchanged"),
            "why": c.get("why")}


def record(root: Path, call: dict[str, Any], *,
           noise: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    entry, inval = float(call["entry_ref"]), float(call["invalidation"])
    stop_pct, why = derive_stop_pct(entry, inval, call["direction"])
    if why:                                    # unreachable via main(), which validates first
        raise ValueError(why)
    cal = calibrated_p(float(call["probability"]))
    sizing = kelly_leverage(cal["used"],
                            float(call["expected_move_pct"]) / stop_pct, stop_pct)
    # HEAT HEADROOM AS A SIZER: trim into what actually fits rather than refusing the setup.
    fit = size_into_headroom(root, str(call["symbol"]), sizing["risk_fraction"])
    if fit["risk"] < sizing["risk_fraction"]:
        sizing = {**sizing, "risk_fraction": fit["risk"],
                  "leverage": round(fit["risk"] / (stop_pct / 100.0), 2) if stop_pct else 0.0,
                  "capped_by": f"{sizing['capped_by']}+{fit['bound']}"}
    sizing["headroom"] = fit
    sizing["calibration"] = cal
    noise_pct = (float(noise["median_adverse_pct"])
                 if noise and noise.get("state") == "MEASURED"
                 and noise.get("median_adverse_pct") is not None else None)
    plan = management_plan(entry, inval, call["direction"],
                           risk_fraction=sizing["risk_fraction"], leverage=sizing["leverage"],
                           noise_pct=noise_pct)
    horizon = float(call["horizon_hours"])
    try:
        charts = json.loads((root / "data/chart_context.json").read_text("utf-8"))
    except (OSError, ValueError):
        charts = None
    row = {**call, "at": now.isoformat(), "paper": True, "venue": "BINANCE-USDM-PERP",
           "setup": setup_features(call, charts), "stop_pct": round(stop_pct, 4),
           "stop_source": "DERIVED from the named invalidation level", "sizing": sizing,
           "noise": noise, "management": plan,
           # the CALIBRATION clock -- when the forecast is scored
           "resolve_by": (now + timedelta(hours=horizon)).isoformat(),
           # the POSITION clock -- a hard time stop far beyond it, so structure decides the exit
           "max_hold_hours": round(horizon * MAX_HOLD_MULT, 2),
           "hard_exit_by": (now + timedelta(hours=horizon * MAX_HOLD_MULT)).isoformat(),
           "entry_order_type": "POST_ONLY_LIMIT at the named level (we bid support, not chase)"}
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    try:
        from libs.self_improvement import forecast_calibration as fc
        # SCORE THE RAW CLAIM, not the size we took: grading the adjusted number would launder the
        # model's own error through the desk's correction and the bias would never be measurable.
        fc.log_forecast(f"conviction:{now.isoformat()}", float(call["probability"]),
                        "directional", resolve_by=row["resolve_by"],
                        claim=f"{call['direction']} {call['symbol']} @{sizing['leverage']}x "
                              f"stop {stop_pct:.2f}% ({str(call['structure'])[:60]}): "
                              f"{str(call['driver'])[:100]}")
    except Exception as exc:                                # noqa: BLE001 -- never lose the call
        row["calibration_log_error"] = str(exc)
    return row


def _ask(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    if args.brief:
        print(json.dumps(brief, indent=2))
        return 0
    dd = sleeve_drawdown(_ROOT)
    if dd["halted"]:
        # Not timidity: a sleeve this far below its high-water mark has evidence its edge is not
        # what it claimed, and adding leveraged size to a broken estimate is how books die (L1.23).
        state = {"status": "HALTED", "why": f"sleeve drawdown rail: {dd['why']}",
                 "drawdown": dd, "at": datetime.now(tz=UTC).isoformat()}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"conviction (R0125): HALTED -- {dd['why']}")
        return 0
    heat = portfolio_heat(_ROOT)
    if heat["state"] == "FULL":
        state = {"status": "HEAT-FULL", "why": heat["why"], "heat": heat,
                 "at": datetime.now(tz=UTC).isoformat()}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"conviction (R0125): HEAT-FULL -- {heat['why']}")
        return 0
    try:
        floors = noise_table()
    except (OSError, ValueError) as exc:
        floors = {"state": "UNMEASURED", "why": str(exc)}
    charts = _chart_brief(_ROOT, heat)
    raw = _ask(_BRIEF.format(instruments=", ".join(INSTRUMENTS),
                             playbook=_playbook_brief(_ROOT), n_support=3,
                             brief=json.dumps(brief, indent=1)[:5000],
                             noise=json.dumps(floors)[:1500],
                             charts=charts,
                             lo=MIN_PROB, hi=MAX_PROB,
                             smin=MIN_STOP_PCT, smax=MAX_STOP_PCT))
    call = parse(raw)
    if call is None:
        state = {"status": "NO-CALL", "why": "no parseable JSON (auth/quota/refusal)",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        noise = None
        if call.get("action") != "PASS" and call.get("symbol") and call.get("horizon_hours"):
            try:
                noise = noise_floor(str(call["symbol"]), float(call["horizon_hours"]),
                                    str(call.get("direction", "LONG")))
            except (ValueError, TypeError, OSError) as exc:
                noise = {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT, "why": str(exc)}
        if call.get("action") != "PASS" and call.get("symbol"):
            heat = {**heat, "fits_risk": size_into_headroom(
                _ROOT, str(call["symbol"]), MAX_RISK_PER_TRADE)["risk"]}
        ok, why = validate(call, noise=noise, heat=heat)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call, "noise": noise}
        elif call.get("action") == "PASS":
            state = {"status": "PASS", "why": why}
        else:
            row = record(_ROOT, call, noise=noise)
            state = {"status": "TRADE", "why": why, "call": row,
                     "leverage": row["sizing"]["leverage"],
                     "peak_leverage": row["management"].get("peak_leverage"), "noise": noise}
    state["drawdown_rail"] = dd
    state["heat"] = heat
    state.setdefault("at", datetime.now(tz=UTC).isoformat())
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"conviction (R0125): {state['status']} -- {state['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
