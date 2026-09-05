"""The gateway's decisions, portable: sizing, heat, roster admission, brackets, plans, gates.

WHY THIS FILE EXISTS. `mt5desk/gateway.py` imports MetaTrader5 at module scope, and that package
exists only on the Windows execution box. Every decision the gateway makes -- how many lots a
stop buys, which sleeves the heat budget admits, whether a conditioned sleeve may trade today,
what bracket a session's range implies, whether a retcode is a rejection or a lost terminal --
therefore lived in a file that no other host could import, and branch coverage of the
capital-moving code on the CI runner was 0.6%: the ten prelude lines before the import that
raises. The desk's tests adapted by AST-extracting functions out of the gateway's source, which
tested them for real but attributed the execution to a compiled string, not to the file, so the
proof existed and the measurement said it did not.

"The most important capital-moving code must have the strongest proof" (principal, 2026-09-05).
This module is that split: every function here is pure over its arguments, or does exactly the
file read that is its stated purpose with the path passed in, and none of them touch the terminal.
`gateway.py` is the thin venue adapter -- it reads the terminal, calls these, and sends what they
decide. Behaviour is byte-for-byte what the gateway did before the split: the same numbers, the
same log lines (returned here as text, written there), the same state keys.

WHAT MAY NOT COME BACK IN. No `import MetaTrader5`, no module-level desk paths, no reads of the
gateway's own state dict. A function that needs a path or a clock takes it as an argument, so a
test can hand it a tmp_path and a fixed time and cover every branch on any host.
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

#: The desk root on sys.path, guarded: `state_allows` imports `research.run_hunt12` the way the
#: gateway always has, and the gateway inserts this same directory unconditionally at import.
_DESK = Path(__file__).resolve().parent.parent
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

#: IMPORTED, NOT RESTATED. The risk budget is defined once, in `gateway_config_fallback`, for the
#: reason that module states: research code on Linux could not import the gateway, so a second
#: literal here would be the drift the single-source test fences.
from mt5desk.gateway_config_fallback import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    Q_OPT,
)
from mt5desk.sizing import (  # noqa: E402
    MAX_RISK_FRAC,
    authority_ramp,
    clamp_risk_frac,
    decay_factor,
)

# ------------------------------------------------------------------------------------ constants

DIST_USD = 19.1         # ~1.2xATR stop distance (USD/oz), used for auto lot scaling

#: GOLD'S contract size and a frozen EUR/USD rate. THESE ARE NO LONGER THE SIZING PATH and must
#: never become it again -- see `_eur_per_price_unit` and `mt5desk.risk_units`. They priced EVERY
#: sleeve's stop as `dist * CONTRACT_OZ * FX_EUR` = `dist * 92`, which is gold's economics applied
#: to whatever symbol the sleeve named. Measured against the venue's own tick values, one price
#: unit per lot is worth EUR 0.86 on BTCUSD, 86.41 on XAUUSD, 542.40 on every JPY cross and
#: 86,414 on EURUSD, so the constant was wrong by 107x in one direction and 939x in the other.
#:
#: The live consequence, measured at EUR 1,683.89 equity on 2026-08-20: a promoted CADJPY sleeve
#: on a 0.50 stop sized to 0.46 lot, reported EUR 21.16 at risk (1.26%, on policy) and actually
#: risked EUR 124.75 -- 7.41% of equity, 5.90x the policy -- while `cap_by_heat` charged it gold's
#: 0.98% and admitted three such sleeves for a believed 2.94% book against a true 22.2%.
#:
#: KEPT, NOT DELETED, because they remain the honest fallback for gold when no tick data can be
#: read at all, and because deleting them would silently change `MIN_LOT_RISK_EUR` for readers.
CONTRACT_OZ = 100
FX_EUR = 0.92

#: The armed book's symbol. Named rather than spelled inline so a caller that omits `symbol`
#: is asking for gold DELIBERATELY, and a grep for the default finds every such site.
GOLD_SYMBOL = "XAUUSD"
RR = 2.0
ATR_N = 20
#: CEILING for a bracket whose session the desk cannot identify, in hours. NOT the normal rule:
#: `bracket_deadline` derives each sleeve's expiry from its OWN window, and this is only what a
#: promoted family sleeve with an unrecognised window falls back to.
#:
#: A FLAT TTL IS A PROXY FOR THE SESSION AND IT IS WRONG FOR MOST OF THE BOOK. Six hours suits
#: gold_asia (07:00 -> 13:00) and nothing else: london_am would run four hours into the
#: afternoon session, and afternoon would outlive the 19:30 force-close entirely. The bracket
#: belongs to the session whose range formed it, so that session is what must end it.
BRACKET_TTL_HOURS = 6.0

#: HOW FAR THE BOOK MAY SLIDE PAST THE BUDGET TO KEEP A VALIDATED LEG, in fractions of equity.
#:
#: MEASURED 2026-09-02: the armed gold book priced at 20.3% against a 20.0% budget and
#: `cap_by_heat` deferred `gold_afternoon` -- a validated, human-armed session amputated over
#: THREE TENTHS OF ONE POINT. The cost of that trade is not the 0.3%: it is a whole session of
#: the day going untraded, and the leg's price floats with its stop distance, so the same book
#: was 13.1% earlier the same afternoon. A budget that drops a third of the book on a rounding
#: edge is measuring volatility, not risk.
#:
#: TWO POINTS, AND THE HARD BAR STILL BINDS ABSOLUTELY. The slide is a tolerance, never a new
#: budget: admission is capped at min(budget + slide, MAX_HEAT_CEILING), so 30% remains
#: unreachable and a book genuinely far over budget is still trimmed. On this book's 33.7R worst
#: run, 20% costs 90.2% and 22% costs 92.4% -- the slide is not a different risk posture, it is
#: the same one without a cliff at the boundary. (principal, 2026-09-02)
HEAT_SLIDE = 0.02

CANCEL_HOUR = 20.5      # end-of-day backstop; the per-bracket TTL above is the real limit
CLOSE_HOUR = 19.5       # force-close positions at 19:30 UTC
PROMOTED_MIN_EQUITY = 300.0  # EUR: below this, promoted sleeves stay dormant
                             # (0.01 lot at 300 EUR ~= 5.9% risk/trade ~= validated 5.5%)

# (label, signal_hour, range window)  range None => [0, signal_hour)
# ny_open QUARANTINED 2026-08-17: exp +0.029R, PF 1.05, maxDD -52.8R (rank 9).
# Must re-earn admission via a genuinely different conditioning rule.
GOLD_WINDOWS = [
    ("asia", 7, None),
    ("london_am", 13, (10, 13)),
    ("afternoon", 17, (14, 17)),
]

#: EUR put at risk by the venue's smallest tradeable position on gold. Below the equity where
#: this equals Q_OPT, the FLOOR sets the risk and the policy does not -- deliberately kept, so a
#: small account can trade and compound up rather than being locked out, but never silently.
#:
#: STILL COMPUTED FROM THE LEGACY CONSTANTS, deliberately: it is a module-scope value and a
#: module-scope read of the live tick value would freeze at import for the life of the daemon
#: (L1.66). Callers that need the true figure ask `min_lot_risk_eur(symbol, dist)`.
MIN_LOT_RISK_EUR = 0.01 * DIST_USD * CONTRACT_OZ * FX_EUR   # ~17.57 (true gold figure ~16.51)

#: The k_eff the base budget is calibrated to: the armed 3-leg gold book, whose measured
#: cross-sleeve correlation is 0.165 -> 2.26 independent bets.
_HEAT_BASE_KEFF = 2.26

#: Legs in the book that -DD figure was measured on (asia, london_am, afternoon). The budget is
#: expressed as total heat = per-trade risk x legs, so this converts one into the other.
_HEAT_BASE_LEGS = 3

#: THE OUTER ENVELOPE -- the total heat the desk may never cross, whatever any optimiser
#: computes. Imported, never restated: `gateway_config_fallback` is where the desk's risk budget
#: is defined, for the same reason Q_OPT lives there.
#:
#: RAISED 0.15 -> 0.30 (principal, 2026-09-02) AND ITS MEANING CHANGED. At 0.15 this was the
#: operative limit and the growth bottleneck: `heat_budget()` returned its 3.81% base on every
#: call the desk has ever made, because k_eff is measured from a live ledger that was empty until
#: 2026-09-01 -- so the account ran at a fifth of its own stated budget and nothing said so. It is
#: now a CATASTROPHE BACKSTOP above a 20% utilisation target, and 30% is where the arithmetic
#: turns: across 256 sampled worlds the robust score is positive at 20% and 25% and NEGATIVE at
#: 30%. Past here the book loses wealth in the worlds it must survive.
MAX_HEAT_CEILING = HEAT_HARD_CEILING

#: How stale the allocator's book may be before the gateway stops believing its heat number. One
#: hour: the allocator's own heavy clock. A stale artifact falls back to the derived formula
#: below -- fail-closed, because an old book is a claim about an opportunity set that has moved.
_ALLOC_MAX_AGE_S = 3600

#: MT5 retcodes this desk has actually seen, and what each one means for the operator.
#: A bare number in a state file is not a diagnosis, and the difference between these
#: two is the difference between a five-minute fix and four days of silence.
RETCODE_MEANING = {
    10015: ("Invalid price",
            "the PENDING ORDER PRICE sits inside the broker's stops/freeze distance. "
            "A buy_stop must be at least stops_level points ABOVE the current ask and a "
            "sell_stop the same distance BELOW the bid. Session-range brackets hit this "
            "whenever price is already sitting on the range edge when the order goes out."),
    10017: ("Trade disabled",
            "the ACCOUNT or TERMINAL will not accept orders at all. Check "
            "'Allow algorithmic trading' in Options > Expert Advisors, that the account "
            "is not read-only or an expired demo, and that the symbol is enabled for "
            "trading rather than quotes-only."),
    10016: ("Invalid stops",
            "the SL or TP is inside the stops/freeze distance from the entry."),
    10019: ("No money", "insufficient free margin for the requested volume."),
    10018: ("Market closed", "the venue is shut for this symbol."),
    10027: ("AutoTrading disabled by client",
            "the terminal's AutoTrading button is off. One click, in the terminal."),
    10014: ("Invalid volume", "the lot is below the venue minimum or off its step."),
}

#: Consecutive placement passes where EVERY order was rejected, after which the
#: gateway pauses itself. Two, because one can be a bad minute at the open and
#: three is another whole day of a desk that is not trading and does not know it.
MAX_TOTAL_REJECTIONS = 2

#: Minimum improvement, in R, before a stop modification is worth sending. A modify costs a
#: round trip to the broker and a chance of rejection; nudging a stop by a fraction of a tick
#: every pass spends both for nothing. Expressed in R rather than price so it means the same
#: thing on gold and on EURUSD.
MIN_RATCHET_IMPROVEMENT_R = 0.05

#: Retcodes the venue answers a placed or done order with. The one success test on this desk.
ACCEPTED_RETCODES = (10008, 10009)


# ------------------------------------------------------------------------------------- sizing

def _eur_per_price_unit(symbol: str, info: object | None = None) -> float:
    """EUR risked per 1.0 of price movement per 1.0 lot of `symbol`.

    THE ONE CONVERSION EVERY SIZING FUNCTION BELOW GOES THROUGH. Live `symbol_info` first --
    `tick_value` carries today's FX rate and is therefore the only current answer -- then the
    `universe.json` snapshot, then, for GOLD ALONE, the legacy constants.

    The gold fallback is not a house average: it is gold's own contract size, and it is reached
    only when the terminal and the snapshot have both failed for the one symbol whose economics
    are hardcoded correctly. For any other symbol an unreadable tick value RAISES, because
    returning 92 for a JPY cross is exactly the defect this function exists to delete, and a
    number that looks plausible is worse than a refusal the caller must handle (L1.28a).
    """
    from mt5desk import risk_units as _ru

    try:
        return _ru.eur_per_price_unit(symbol, info)             # type: ignore[arg-type]
    except _ru.RiskUnitUnmeasured:
        if symbol == GOLD_SYMBOL:
            return float(CONTRACT_OZ * FX_EUR)
        raise


def min_lot_risk_eur(symbol: str = GOLD_SYMBOL, dist_price: float | None = None,
                     info: object | None = None) -> float:
    """EUR risked by the venue's smallest ticket on `symbol` at `dist_price`.

    Read fresh on every call rather than cached at import, so a re-fetched universe or a moved
    FX rate reaches the next trade rather than the next restart.
    """
    d = float(dist_price) if dist_price and dist_price > 0 else DIST_USD
    return 0.01 * d * _eur_per_price_unit(symbol, info)


def _lot_steps(raw_lot: float) -> float:
    """Snap a raw lot DOWN to the venue's 0.01 grain. Never up.

    This was `round()` -- to nearest -- and that let realised risk EXCEED the policy by up to half
    a lot step. It was invisible while Q_OPT sat 41% below the heat budget, because there was
    slack to absorb the overshoot. Now that Q_OPT is derived from the drawdown tolerance, the base
    budget is exactly `Q_OPT x 3 legs`, so an upward round on every leg puts the armed gold book
    OVER its own cap and `cap_by_heat` amputates a validated leg: at EUR 8,000 nearest-rounding
    gave 0.06 lot (1.32% x 3 = 3.95% against a 3.81% budget) and dropped gold_afternoon.

    Rounding down costs a little size in the gaps between lot steps -- 0.05 rather than 0.06 at
    EUR 8,000 -- and buys the invariant that realised risk is never above the stated policy. The
    0.01 minimum below is the sole documented exception, where the venue's floor overrides the
    policy upward and `realised_q` reports exactly that.
    """
    return math.floor(raw_lot / 0.01 + 1e-9) * 0.01


def stop_distance(spec: dict | None) -> float | None:
    """The bracket's OWN stop, in USD/oz. None when the spec cannot supply one.

    None rather than a fallback: a caller that cannot see the real stop must
    decide what to do about that, and silently substituting the house average is
    the exact defect this function exists to end.
    """
    for side in ("buy_stop", "sell_stop"):
        leg = (spec or {}).get(side) or {}
        p, sl = leg.get("price"), leg.get("sl")
        if p is not None and sl is not None and abs(p - sl) > 1e-9:
            return abs(float(p) - float(sl))
    return None


def realised_q(equity: float, dist_usd: float | None = None,
               symbol: str = GOLD_SYMBOL, info: object | None = None,
               lot: float | None = None) -> float:
    """The risk fraction the account WILL actually run, after the 0.01-lot floor.

    Not the same as Q_OPT whenever equity is small, and that gap is the whole point of this
    function existing. `auto_lot` used to clamp to 0.01 inside a `min(max(...))` and return only
    the lot, so a book configured for 0.75% could run at 5.9% with nothing in the code, the log
    or the state file ever saying so. A policy number that the venue silently overrides is not a
    policy.

    `dist_usd` IS THE SLEEVE'S OWN STOP where the caller knows it. See `auto_lot`.

    `symbol` IS THE SLEEVE'S OWN INSTRUMENT, for the same reason and with a larger error. This
    read `dist * CONTRACT_OZ * FX_EUR` for every sleeve, so it reported gold's risk fraction for
    a JPY cross and understated it 5.90x.
    """
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    per_unit = _eur_per_price_unit(symbol, info)
    if lot is None:
        # No lot given: recompute at Q_OPT -- right for the Q_OPT-sized book, FICTION for a
        # clamp-sized promoted sleeve (printed 1.16% while the lot ran 2.9%). Callers holding
        # the actual lot pass it; q_charge already bills the heat cap honestly either way.
        lot = max(_lot_steps(Q_OPT * equity / (d * per_unit)), 0.01)
    return float(lot * d * per_unit / equity) if equity > 0 else 0.0


def auto_lot(equity: float, dist_usd: float | None = None,
             symbol: str = GOLD_SYMBOL, info: object | None = None,
             q: float | None = None) -> float:
    """Fixed-fractional sizing: Q_OPT of equity per trade, floored at the venue minimum.

    `q` overrides Q_OPT for callers whose risk fraction is sleeve-specific (the promoted
    path since 2026-08-25); None keeps the derived house Q_OPT for the armed book.

    `dist_usd` IS THE SLEEVE'S OWN STOP, AND PASSING IT IS NOT OPTIONAL IN THE LIVE PATH.

    This sized every sleeve from the house constant DIST_USD = 19.1 while the caller had the
    real bracket in hand on the line above. Fixed-fractional sizing means lot = risk_budget /
    stop_distance, so using a stop 2.8x narrower than the real one produces a position 2.8x
    larger than the budget bought. The live brackets on 2026-08-14 were:

        sleeve        actual stop     vs DIST_USD 19.1     realised risk multiple
        asia            $53.40             2.80x                   2.80x
        afternoon       $48.64             2.55x                   2.55x
        london_am       $27.91             1.46x                   1.46x
        ny_open         $18.65             0.98x                   0.98x

    So two of four sleeves ran at roughly 2.5-2.8x the stated policy, at EVERY equity, while
    `realised_q` reported the policy figure and the heat cap admitted legs against it. The
    three-leg book believed it was at its 3.81% budget and was closer to 8%. Nothing was wrong
    with either number in isolation; the constant was simply not the thing being traded.

    Session-range stops are the reason the gap is this large. These brackets are the session
    high to session low, so the stop is as wide as the session was -- a quantity that varies by
    a factor of three across the day and has no reason to sit near a single average.

    THE FLOOR IS A DECISION, NOT A ROUNDING ARTIFACT. 0.01 lot risks ~EUR 17.57 on gold at the
    house distance, so the smallest position the venue will accept already implies a fixed EUR
    risk, and the fraction that represents falls as equity grows (figures below at DIST_USD;
    a wider sleeve scales them by its own multiple):

        equity  realised q   worst historical DD (3-leg book, -33.7R)
          300      5.86%          -86.9%     <- ~full Kelly. This is where accounts die.
          500      3.51%          -70.1%
          800      2.20%          -52.7%
        1,684      1.04%          -29.8%     <- current account; survivable
        2,300      0.76%          -22.7%     <- last equity the floor still binds at
        3,000      1.17%          -32.7%     <- policy reachable; q now tracks Q_OPT from here
       25,000      1.27%          -34.9%

    Note the DIP around EUR 2,300 and not a monotone fall: once the raw lot clears 0.01 the floor
    stops binding, and realised q drops to whatever the 0.01 grain allows before climbing back
    toward Q_OPT as equity makes the grain finer. Sizing is a step function, not a curve.

    Kept floored rather than refusing to trade, because a book that cannot open a position also
    cannot compound out of the range where the floor binds. The cost of that choice is real and
    it is highest at the smallest sizes, which is precisely when it is least visible on a
    statement -- so the realised fraction is computed explicitly by `realised_q` and recorded by
    the caller instead of being inferred from a lot size after the fact.
    """
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    qq = float(q) if q and q > 0 else Q_OPT
    lot = _lot_steps(qq * equity / (d * _eur_per_price_unit(symbol, info)))
    return float(min(max(lot, 0.01), 5.0))


def ramped_fraction(risk_frac: object, live_n: int, decay_faded: object = None) -> float:
    """The effective risk fraction of a NON-BOOK promoted sleeve: base clamp x authority x fade.

    ONE LADDER, TWO READERS. `promoted_lot` sizes the order from this number and the gateway
    bills the heat cap the same number as `q_charge`; they used to compute it separately, and
    two copies of a risk ladder is how one of them is silently edited. The ramp multiplies the
    RISK FRACTION, not the lot after the fact, so authority is expressed in equity terms, and
    the L1.59 fade sits OUTSIDE the clamp because the clamp floors at 3% and would otherwise
    read a halved fraction straight back up (measured: a FADED sleeve sized 3.0 lots against a
    healthy 3.0). Reduce-only by construction; it can never raise a fraction.
    """
    return clamp_risk_frac(risk_frac) * authority_ramp(live_n) * decay_factor(decay_faded)


def promoted_lot(equity: float, live_n: int, dist_usd: float | None = None,
                 symbol: str = GOLD_SYMBOL, info: object | None = None,
                 risk_frac: float | None = None,
                 decay_faded: object = None, from_book: bool = False) -> float:
    """Dynamic lot for promoted sleeves: risk-fraction sizing x authority ramp.

    RISK BASE (principal order 2026-08-25): promoted sleeves target
    `clamp_risk_frac(risk_frac)` of equity per trade -- 3% base, dynamic-up to 10% only when
    the promoter records the economic justification in the sleeve row. THE RAMP MULTIPLIES THE
    RISK FRACTION, not the lot after the fact, so authority is expressed in equity terms:
    0.75% effective before 50 live trades (the same neighbourhood as the armed book's derived
    Q_OPT -- deliberate, per the estimation-fragility ladder in `gateway_config_fallback`),
    1.5% before 200, the full base only after 200 forward-proven live trades. A sleeve reaches
    3% by EARNING it.

    `dist_usd` is the sleeve's own stop and is passed through for the same reason
    `auto_lot` takes it: a promoted sleeve on a wide session runs the same 2.8x
    overshoot as an armed one, and the ramp would have made it look deliberate.

    `symbol` IS THE SLEEVE'S OWN INSTRUMENT. Promoted sleeves are the ONLY non-gold things the
    gateway trades, so this function was the single place where gold's constants were guaranteed
    to be applied to something that is not gold. `roster` rewrites every promoted sleeve's lot
    field to "auto_ramp", so the literal 0.01 the promoter writes never reaches the venue and
    this path is always taken.
    """
    # L1.59 FADE, OUTSIDE the clamp (gap-fixer 2026-08-29). `clamp_risk_frac` floors at 3%, so
    # the halved fraction `decay_monitor` wrote into data/sleeves.json was read straight back up
    # and a FADED sleeve sized identically to a healthy one -- measured, 3.0 lots vs 3.0 lots.
    # The flag is now the single source of truth and it is applied in `ramped_fraction`,
    # alongside the ramp, which is the same shape for the same reason: authority and decay both
    # scale RISK, not the lot after the fact. Reduce-only by construction.
    if from_book:
        # THE ALLOCATOR'S FRACTION IS THE FRACTION (principal, 2026-09-04: the book's 20-30% is
        # deployed, not re-shrunk). h_i was solved on posterior worlds that ALREADY shrink each
        # sleeve by its forward and live evidence, so applying the authority ramp again halved
        # or quartered every leg a second time: MEASURED on the 2026-09-04 forecast log, a 20.5%
        # book whose largest leg (5.1%) reached the venue at 1.3%, and the whole book at ~5%.
        # The clamp is not applied either -- it FLOORS at 3%, which would raise a leg the
        # allocator sized at 1.7%, and CEILS at 10%, which stays as the outer per-trade envelope
        # (raising it is a principal act). The fade flag still applies: it is live decay the
        # daily worlds have not yet absorbed, and it is reduce-only.
        try:
            h_i = float(risk_frac)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            h_i = 0.0
        if not (h_i > 0.0):
            return 0.0
        q_eff = min(h_i, MAX_RISK_FRAC) * decay_factor(decay_faded)
    else:
        q_eff = ramped_fraction(risk_frac, live_n, decay_faded)
    lot = auto_lot(equity, dist_usd, symbol, info, q=q_eff)
    # FLOOR, not nearest. Rounding up here reintroduced the overshoot `_lot_steps`
    # exists to prevent, on exactly the sleeves with the least forward evidence.
    lot = math.floor(lot / 0.01 + 1e-9) * 0.01
    return float(min(max(lot, 0.01), 5.0))


def sleeve_live_n(name: str, ledger: Path) -> int:
    """Closed-trade count for a sleeve from the live ledger at `ledger`."""
    if not ledger.exists():
        return 0
    try:
        n = 0
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("sleeve") == name:
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


# ----------------------------------------------------------------------------- heat and budget

def heat_budget(k_eff: float | None = None) -> float:
    """Total risk the book may carry, scaled by how many INDEPENDENT bets it actually holds.

    A FIXED PERCENTAGE IS THE WRONG INSTRUMENT AND IT CAPS GROWTH PERMANENTLY. At a flat 4% the
    admitted sleeve count converges to five at ANY equity -- 5 at EUR 2,343 and still 5 at EUR
    100,000 -- because `realised_q` converges to Q_OPT once the account clears the 0.01 lot floor.
    The book would stop widening forever, which is the opposite of safe aggressive growth.

    The reason 4% was right for three gold legs is not the number of sleeves, it is that those
    legs are 0.165 correlated and therefore only ~2.26 independent bets. Portfolio drawdown for N
    sleeves at total heat H scales roughly as H / sqrt(k_eff), so holding drawdown fixed lets H
    grow with sqrt(k_eff). Five genuinely independent sleeves are SAFER at 6% than three
    correlated ones at 4%, and a constant refuses to see the difference.

        k_eff 2.26 (gold book today)      -> 4.0%
        k_eff 5.12 (the 9 candidates)     -> 6.0%
        k_eff 9.0                          -> 8.0%

    UNMEASURED k_eff RETURNS THE BASE BUDGET, never the ceiling. The desk has no live
    cross-sleeve correlation yet -- shadow started 2026-08-16 -- and treating "not yet measured"
    as "independent" is the single assumption that would let a correlated book size like a
    diversified one, which is how a portfolio discovers its real correlation during the drawdown
    rather than before it.
    """
    # THE PORTFOLIO BUDGET IS A STATED NUMBER, NOT A PER-TRADE q TIMES A LEG COUNT.
    #
    # WHAT WAS WRONG. This read `q_star = Q_OPT` -- the 1.27% POLICY risk -- times the validated
    # leg count, giving 3.81%. That is correct only while the 0.01-lot floor does not bind. It
    # binds now: MEASURED 2026-09-02 at EUR 603.84 equity, the armed gold book's three legs cost
    # 13.1% because the venue minimum forces ~4.4% per leg. `cap_by_heat` charges what a leg
    # REALLY costs against a budget built from what a leg WOULD cost on a bigger account, so the
    # live gateway log read `admitting 1 at 7.7%, deferring ['gold_london_am', 'gold_afternoon']`
    # on every pass -- two thirds of the human-armed book sitting out because the account shrank.
    #
    # A REJECTED FIX, RECORDED BECAUSE IT LOOKS RIGHT. Raising the budget to the leg's REALISED
    # cost (max(Q_OPT, q_realised) x legs) restores all three legs and is wrong: it grows total
    # heat precisely as equity falls, which is the exact failure
    # `test_a_small_account_gets_fewer_sleeves_not_more_risk` exists to catch, and it caught it.
    # A budget that moves with the account is not a budget.
    #
    # HEAT_TARGET is the principal's stated portfolio budget (20%, 2026-09-02), fixed and
    # equity-independent, so the invariant holds: a smaller account still buys fewer sleeves
    # (4 legs at EUR 600 against 15 at EUR 8,000), it just no longer buys fewer than the armed
    # book needs to exist.
    #
    # WHAT IT COSTS, STATED AND NOT BURIED. The 35% drawdown tolerance is solved against THIS
    # book's 33.7R worst run, so 3.81% <-> 35.0%. At 20% the same run costs 90.2%, and at the
    # 30% ceiling 97.1%. Those numbers describe the THREE-LEG CORRELATED GOLD BOOK; 33.7R is its
    # drawdown, and twenty independent sleeves do not all lose together, so the same heat over a
    # broad book implies far less. That is precisely why `research/heat_policy.py` ramps the
    # allocator's floor with measured out-of-sample breadth instead of asserting 20% on day one,
    # and why the k_eff term below still has to be earned.
    q_star = HEAT_TARGET / _HEAT_BASE_LEGS
    # MULTIPLIED BY THE VALIDATED LEG COUNT, NOT BY k_eff -- and the difference matters. The
    # -33.7R figure is the drawdown of the SUMMED three-leg series, so it already contains how
    # often those legs co-fire; scaling it by k_eff as well double-counts the diversification and
    # returned 2.87%, which is less than the 3.12% the armed gold book actually runs. The first
    # version of this line therefore amputated the very book the budget is calibrated on.
    base = q_star * _HEAT_BASE_LEGS
    if k_eff is None or k_eff != k_eff or k_eff < 1.0:      # NaN is unmeasured too
        return float(min(base, MAX_HEAT_CEILING))
    # More independent bets survive more total heat at the SAME drawdown: portfolio drawdown for
    # N sleeves at heat H scales roughly as H/sqrt(k_eff), so holding drawdown fixed lets H grow
    # with sqrt(k_eff). Breadth is paid for with measured orthogonality.
    scaled = base * math.sqrt(float(k_eff) / _HEAT_BASE_KEFF)
    return float(min(max(scaled, base), MAX_HEAT_CEILING))


def allocator_heat(base: Path, now: float | None = None) -> tuple[float | None, str]:
    """Total heat the E[log W] allocator resolved, or None with the reason it cannot be used.

    THE BUDGET IS AN OUTPUT, NOT A FORMULA. `heat_budget()` derives a number from the drawdown
    tolerance and a breadth estimate, which was the best available answer while nothing solved
    for exposure. `research/pf_allocator.py` now does solve for it -- jointly with which sleeves
    hold it -- so when a fresh, certified, ARMED book exists it is the budget, and the derivation
    is what the desk falls back to when it does not.

    FAILS CLOSED ON EVERY DOUBT. Missing file, stale file, unparseable file, uncertified target,
    unarmed allocator: all return None, and the desk keeps running the derived budget it ran
    yesterday. Nothing here can RAISE heat by accident -- raising it takes a live artifact that
    passed its own certification plus a human-created arm file, which is the same shape as every
    other arming decision on this desk (GENERIC_EXEC_ENABLED, and gold re-arming).

    `base` is the desk root the artifacts live under; `now` is the clock the artifact's age is
    measured against (the wall clock when None), passed in so staleness is testable.
    """
    try:
        if not (base / "data" / "PF_ALLOCATOR_ARMED").exists():
            return None, "allocator not armed (data/PF_ALLOCATOR_ARMED absent)"
        f = base / "reports" / "pf_allocation.json"
        if not f.exists():
            return None, "no pf_allocation.json"
        age = (time.time() if now is None else now) - f.stat().st_mtime
        if age > _ALLOC_MAX_AGE_S:
            return None, f"pf_allocation.json is {age / 60:.0f} min stale"
        art = json.loads(f.read_text(encoding="utf-8"))
        heat = art.get("heat") or {}
        if not heat.get("certified"):
            return None, "allocator did not certify the utilisation target"
        total = float(heat.get("total") or 0.0)
        if not (0.0 < total <= MAX_HEAT_CEILING + 1e-12):
            return None, f"allocator heat {total:.4f} outside (0, {MAX_HEAT_CEILING:.2f}]"
        # A HEAT NUMBER WITH NO GROWTH BEHIND IT IS NOT A BUDGET. Measured 2026-09-02: a pass
        # published 30% total heat carrying annual_growth_pct = -inf -- a book wiped out in at
        # least one sampled world -- and every check above passed it, because they all asked
        # about the heat and none asked whether the optimiser could score the thing it sized.
        g = art.get("growth") or {}
        ann = g.get("annual_growth_pct")
        if not isinstance(ann, (int, float)) or not math.isfinite(float(ann)):
            return None, f"allocator book has no finite growth ({ann!r})"
        return total, f"allocator book ({age / 60:.0f} min old, binding={heat.get('binding')})"
    except Exception as exc:
        return None, f"allocator artifact unreadable ({type(exc).__name__})"


def book_from_allocation(total: float, book: object, book_fallback: object, *,
                         certified: bool, why: str,
                         zeroed: object = None) -> tuple[dict[str, float] | None, str]:
    """The optimiser's PER-SLEEVE target risk fractions, or None with the reason.

    THE BOOK WAS SOLVED AND THEN NOT USED. `allocator_heat` takes the optimiser's TOTAL and the
    marginal ranking takes its ORDER, and each sleeve was then sized by `q_charge` /
    `realised_q` / Q_OPT -- so the one number the optimiser actually solves for, h_i, reached
    nothing. A book of {A: 4.3%, B: 3.7%, C: 2.1%} became "total 10.1%, in that order", which is
    a different allocation to the one that maximised E[log W].

    AUTHORITY IS EARNED, NOT ASSUMED. A dynamic allocator sits above every edge and reallocates,
    so it can destroy compounding faster than any single sleeve. It may size positions only
    while a FRESH certificate says it beat equal-weight, inverse-vol, risk-parity and
    doing-nothing on the desk's own sampled worlds at equal heat -- `certified` is that verdict
    and `why` its reason. Not certified, and the DYNAMIC weights have no authority; the book the
    desk sizes is then the best BASELINE the contest scored at the same total heat
    (`book_fallback`), because the floor is deployed either way (principal, 2026-09-04: 20%
    minimum, 24/7). A stale or failed proof changes WHO allocates the floor, never WHETHER it
    is allocated.

    ZERO IS AN ANSWER, AND IT COULD NOT BE GIVEN (principal, 2026-09-05: "five minutes/hour/
    session later, it can be 0%"). `pf_allocation.json`'s `book` is filtered to heat > 1e-5, so a
    sleeve the optimiser ZEROED simply vanished from it -- and a name not in the book reads as
    `from_book = False` in the gateway, which falls through to `promoted_lot`'s ramp path and
    `sizing.clamp_risk_frac`, which FLOORS at BASE_RISK_FRAC. The allocator's "hold none of this"
    therefore reached the venue as 3% of equity times the authority ramp. `zeroed` is the
    allocator's explicit list of ROSTERED sleeves it gave no heat (`book_zeroed`), and those names
    are carried into the returned book at 0.0 so the gateway's existing "allocator gave this
    sleeve no heat; skipped" path -- present at every placement site and until now unreachable --
    actually fires.

    STRICTLY ADDITIVE AND REDUCE-ONLY. Absent or unreadable `zeroed` leaves the answer exactly as
    it was; a zero entry can only lower a sleeve's size, never raise one; zeros do not change the
    book's sum, so the drift check against `total` is unaffected; and the empty-book refusal is
    decided BEFORE any zero is added, so a book of nothing but zeros still reads as "the allocator
    declined to allocate" rather than as an instruction to size everything at zero.

    Pure over the artifact's parsed pieces: `total` is the certified heat `allocator_heat`
    returned, `book` and `book_fallback` are the artifact's own fields. The gateway reads the
    files and the certificate; this decides what they mean.
    """
    if not certified:
        fb = book_fallback or {}
        try:
            book_ = {str(k): float(v) for k, v in (fb.get("book") or {}).items()
                     if float(v) > 0.0}
        except (TypeError, ValueError):
            book_ = {}
        if not book_:
            return None, f"allocator may rank but not size: {why}; no fallback book either"
        drift = abs(sum(book_.values()) - total)
        if drift > 0.005:
            return None, (f"fallback book sums to {sum(book_.values()):.4f}, heat says "
                          f"{total:.4f}")
        return book_, (f"floor deployed with baseline {fb.get('name', '?')} "
                       f"({len(book_)} sleeve(s)); dynamic weights withheld: {why}")
    try:
        book_ = {str(k): float(v) for k, v in (book or {}).items() if float(v) > 0.0}
    except Exception as exc:
        return None, f"pf_allocation book unreadable ({type(exc).__name__})"
    if not book_:
        # An EMPTY book is a real answer -- "hold nothing" -- but it is not a sizing instruction,
        # and returning {} here would read to the caller as "size everything at zero" rather than
        # "the allocator declined to allocate". The no-new-exposure path already handles that.
        return None, "allocator book is empty (no positive-heat sleeve)"
    drift = abs(sum(book_.values()) - total)
    if drift > 0.005:
        # The book and the total come from the same artifact and must agree. A disagreement means
        # one of them was rewritten independently, and sizing on a book that does not sum to the
        # budget the heat cap enforces would over- or under-deploy silently.
        return None, f"book sums to {sum(book_.values()):.4f}, heat says {total:.4f}"
    n_zero = 0
    try:
        for name in (zeroed or {}):
            if str(name) not in book_:
                book_[str(name)] = 0.0
                n_zero += 1
    except TypeError:
        n_zero = 0                      # unreadable list: the book stands exactly as it was
    if not n_zero:
        return book_, f"allocator book authoritative ({len(book_)} sleeve(s)); {why}"
    return book_, (f"allocator book authoritative ({len(book_) - n_zero} sleeve(s), {n_zero} held "
                   f"at zero by this solve); {why}")


def allocator_rank(base: Path, now: float | None = None) -> dict[str, float] | None:
    """Marginal dE[log W] per sleeve from a FRESH allocation artifact under `base`, else None.

    SILENT ON ABSENCE, NEVER WRONG ON IT: no artifact, a stale one, or an unreadable one all
    return None, and `allocator_order` then leaves the caller's order standing.
    """
    try:
        f = base / "reports" / "pf_allocation.json"
        if not f.exists() or (time.time() if now is None else now) - f.stat().st_mtime \
                > _ALLOC_MAX_AGE_S:
            return None
        mg = json.loads(f.read_text(encoding="utf-8")).get("marginal_delta_elog") or {}
        if not isinstance(mg, dict) or not mg:
            return None
        return {str(k): float(v) for k, v in mg.items()}
    except Exception:
        return None


def allocator_order(sleeves: list[dict], rank: dict[str, float] | None) -> list[dict]:
    """Reorder `sleeves` by marginal dE[log W], best first; unpriced sleeves keep their place.

    WHAT THIS REPLACES. `cap_by_heat` trims in list order and the roster emits gold first, so
    the armed gold book was senior to everything else by position. The stated justification was
    that gold is "the one book with forward evidence behind it" -- which stopped being true once
    the forward clocks filled, and a seniority rule that outlives its reason silently becomes a
    rule that the oldest sleeve wins. Ordering by what each sleeve is worth to the book makes the
    trim drop the cheapest growth rather than the newest name.

    No `rank` (absent or stale artifact -- see `allocator_rank`) and the caller's order stands.
    """
    if not rank:
        return sleeves
    known = [s for s in sleeves if str(s.get("name")) in rank]
    unknown = [s for s in sleeves if str(s.get("name")) not in rank]
    known.sort(key=lambda s: -rank[str(s["name"])])
    # Unknown sleeves go LAST, not first: a sleeve the allocator has never priced has no claim
    # on the budget ahead of one it has measured and valued.
    return known + unknown


def cap_by_heat(sleeves: list[dict], equity: float,
                per_sleeve_q: float | None = None,
                k_eff: float | None = None, *,
                allocation: tuple[float | None, str] | None = None,
                rank: dict[str, float] | None = None) -> tuple[list[dict], str | None]:
    """Trim `sleeves` so their combined risk stays inside the heat budget.

    Returns the admitted sleeves and a note when anything was dropped, because a silently
    shortened book is indistinguishable from a book that had nothing to trade.

    THE ALLOCATOR'S BOOK IS THE BUDGET WHEN THERE IS ONE. `allocation` is what the gateway's
    `allocator_heat()` answered -- the solved total, or None with the reason -- and `heat_budget`
    is the derivation the desk falls back to. Passed in rather than read here so this stays pure;
    the gateway consults the artifact and hands over the verdict. No verdict at all is treated
    exactly like an unusable one: fail closed to the derivation, never raise heat by accident.

    ORDER IS BY MARGINAL dE[log W], not by the caller's list position. It used to be the latter,
    justified by the roster emitting gold first: "a cap that dropped sleeves arbitrarily could
    silently retire the one book with forward evidence behind it in favour of three that have
    none." That was true when gold was the only sleeve with forward evidence and stopped being
    true when the forward clocks filled -- at which point a seniority rule with a dead reason is
    just a rule that the oldest sleeve wins, and the desk cannot displace a worse edge with a
    better one. `rank` is the allocator's marginal map; absent, the caller's order still stands,
    so the old behaviour is the fallback, not the rule.

    EACH SLEEVE IS CHARGED ITS OWN q, NOT THE BOOK'S. This multiplied ONE q -- gold's, because
    `realised_q` defaulted to gold's contract economics -- by the sleeve COUNT, so a book of
    heterogeneous instruments was capped as though every leg cost what a gold leg costs. The two
    errors compounded: the sizing path put a JPY cross on 5.90x its budget, and this function
    then billed that sleeve at gold's 0.98%, so three of them read as a 2.94% book against a true
    22.2%. A cap that cannot see what a leg actually costs is not a cap.
    """
    if equity <= 0 or not sleeves:
        return list(sleeves), None
    solved, why = allocation if allocation is not None else (None, "no allocator verdict given")
    budget_src = why if solved is not None else f"derived (allocator unusable: {why})"
    # ORDERED BY WHAT EACH SLEEVE IS WORTH, not by where the caller put it. See allocator_order.
    sleeves = allocator_order(sleeves, rank)
    # Per-sleeve q: an explicit scalar override still applies to every sleeve (that is what a
    # caller asking for one means), otherwise each sleeve is priced on ITS OWN instrument.
    qs: list[float] = []
    #: Parallel to `qs`: this leg was priced at zero by the ALLOCATOR, not by a failed
    #: measurement. Kept separate so the unmeasurable-leg fallback below cannot overwrite it.
    zeroed_by_allocator: list[bool] = []
    for s in sleeves:
        zeroed_by_allocator.append(False)
        if per_sleeve_q is not None:
            qs.append(float(per_sleeve_q))
            continue
        # AN EXPLICIT ZERO IS A PRICE, NOT A MISSING ONE. `gateway` sets `q_charge` from the
        # allocator's own fraction for a sleeve in the solved book, and `book_zeroed` puts a
        # sleeve the solve gave NO heat into that book at exactly 0.0 -- `promoted_lot` then
        # returns no lot for it and it places nothing. Billing it at its measured stop cost would
        # reserve budget nothing will use and could defer a leg the book actually wanted. It stays
        # in the returned roster either way, because dropping it here would orphan any bracket it
        # still has open. Before `book_zeroed` existed this value could not BE zero
        # (`sizing.clamp_risk_frac` floors at the base fraction), so nothing that worked before
        # reads differently now.
        _qc = s.get("q_charge")
        if isinstance(_qc, (int, float)) and not isinstance(_qc, bool) and float(_qc) == 0.0:
            zeroed_by_allocator[-1] = True
            qs.append(0.0)
            continue
        # A sleeve annotated with its own effective fraction (risk_frac x ramp, set by the
        # caller) is billed exactly that -- the sizing path and the heat path must price the
        # same trade at the same number or the budget is fiction.
        if s.get("q_charge") and float(s["q_charge"]) > 0:
            qs.append(float(s["q_charge"]))
            continue
        try:
            d = s.get("dist")
            sym_name = s.get("symbol", GOLD_SYMBOL)
            if d and float(d) > 0:
                qs.append(realised_q(equity, float(d), sym_name))
            elif sym_name == GOLD_SYMBOL:
                # Gold has a house nominal stop in the right units, and using it KEEPS THE
                # FLOOR VISIBLE: 0.01 lot is a larger fraction of a smaller account, so a
                # shrinking account must see its per-sleeve q RISE. A flat policy figure here
                # would hide exactly the risk a heat budget exists to catch.
                qs.append(realised_q(equity, None, sym_name))
            else:
                # NO STOP KNOWN AND NO NOMINAL IN THIS INSTRUMENT'S UNITS. DIST_USD is 19.1
                # dollars per ounce; read as a JPY cross's stop it is ~19 yen, which prices a
                # 0.01 lot at 6.2% and would defer every JPY sleeve forever for a distance
                # nobody ever intended to trade -- the timidity half of this same defect.
                # Q_OPT is what the sizer now achieves whenever the floor does not bind, and on
                # these instruments it binds only at stops far wider than they trade (a JPY
                # cross needs a 3.9 yen stop at current equity). The first bracket replaces
                # this estimate with the sleeve's own measured stop.
                qs.append(float(Q_OPT))
        except Exception:
            # UNMEASURABLE IS CHARGED AT THE MOST EXPENSIVE MEASURED LEG, never at gold's by
            # default. An instrument whose risk cannot be priced must not be the cheapest thing
            # in the book (L1.28a); if nothing at all is measurable the budget admits nobody.
            qs.append(float("nan"))
    known = [q for q in qs if q == q and q > 0]
    fallback = max(known) if known else 0.0
    budget = solved if solved is not None else heat_budget(k_eff)
    # An allocator-zeroed leg keeps its zero; every OTHER unpriceable leg is still charged at the
    # most expensive measured one, exactly as before.
    qs = [(0.0 if z else (q if q == q and q > 0 else fallback))
          for q, z in zip(qs, zeroed_by_allocator, strict=True)]
    if fallback <= 0 and not all(zeroed_by_allocator):
        note = ("PORTFOLIO HEAT CAP: no sleeve's risk could be priced in account currency; "
                "admitting none rather than sizing from another instrument's constants")
        return [], note
    # THE SLIDE. A validated leg is not dropped for overshooting the budget by a rounding edge;
    # see HEAT_SLIDE. The hard ceiling is applied here and not inside it, so no future change to
    # the slide can lift the book past MAX_HEAT_CEILING.
    limit = min(budget + HEAT_SLIDE, MAX_HEAT_CEILING)

    admitted: list[dict] = []
    dropped: list[str] = []
    used = 0.0
    for s, q in zip(sleeves, qs, strict=True):
        # CONTINUE, NOT BREAK. Stopping at the first sleeve that does not fit throws away every
        # sleeve behind it, however cheap -- so one expensive leg near the front could defer a
        # whole tail of legs the budget had room for. Combined with the value ordering above this
        # is a greedy fill by marginal growth per unit of heat: the budget buys the most it can,
        # and what is deferred is the cheapest growth rather than everything after the misfit.
        if used + q > limit + 1e-12:
            dropped.append(str(s.get("name", "?")))
            continue
        admitted.append(s)
        used += q
    if not dropped:
        return list(sleeves), None
    note = (f"PORTFOLIO HEAT CAP: {len(sleeves)} sleeves totalling {sum(qs):.1%} "
            f"exceed {limit:.1%} (budget {budget:.1%} + {HEAT_SLIDE:.1%} slide, "
            f"ceiling {MAX_HEAT_CEILING:.0%}) [{budget_src}] "
            f"(k_eff {'unmeasured' if k_eff is None else format(k_eff, '.2f')}); "
            f"admitting {len(admitted)} at {used:.1%}, deferring {dropped}")
    return admitted, note


# ---------------------------------------------------------------------------- roster admission

def load_sleeves(path: Path) -> list[dict]:
    """Promoted sleeves from a sleeves.json at `path` (writer: research/promoter.py), LIVE only."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
    except Exception:
        return []


def load_retired_gold(path: Path) -> dict:
    """Retired gold windows from the promoter's file at `path`, or {} when absent/unreadable.

    FAILS OPEN ON PURPOSE, and this is the one place in the decision core where that is right:
    an unreadable file must not silently stop a live book that is otherwise trading correctly.
    A retirement that does not apply is visible in the next promoter run and in the gateway's
    log line; a book that stops because a JSON file got truncated is an outage with no author.
    """
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def ledger_rows(path: Path) -> list[dict]:
    """Closed trades recorded by the desk at `path`. Torn final lines are skipped, never fatal."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def roster(retired_gold: dict, promoted: list[dict]) -> tuple[list[dict], list[str]]:
    """All active sleeves -- gold book + promoted, with window metadata -- and the log lines.

    Returns `(sleeves, notes)`: the roster in emission order, and one note per gold window the
    promoter has retired, for the gateway to log. Pure over the two files' parsed contents.
    """
    sleeves: list[dict] = []
    notes: list[str] = []
    # THE GOLD BOOK DECAYS LIKE EVERYTHING ELSE NOW (principal, 2026-09-01). research/promoter.py
    # walks these three names against the same retire rules it applies to promoted sleeves and
    # writes the loser to GOLD_RETIRED.json with its reason. Until 2026-09-01 the armed gold book
    # was exempt from retirement entirely -- so the desk's ONLY live sleeves were the only ones
    # with no automatic decay protection, because the retire rules walked sleeves.json, which
    # is empty. ABSENT FILE = NOTHING RETIRED, which is the behaviour up to now; and re-arming
    # stays a person's act, because undoing a retirement means deleting the entry by hand.
    for label, sig_hour, rng in GOLD_WINDOWS:
        name = f"gold_{label}"
        if name in retired_gold:
            notes.append(f"GOLD {name}: RETIRED "
                         f"({retired_gold[name].get('reason', 'no reason recorded')}); "
                         f"not emitted this pass")
            continue
        sleeves.append({"name": name, "symbol": "XAUUSD",
                        "window": label, "sig_hour": sig_hour, "rng": rng,
                        "lot": "auto", "status": "LIVE"})
    for s in promoted:
        # GENERIC FAMILY SLEEVES (GAP 124, 2026-08-25): hunt-certified sleeves the promoter
        # admitted with exec="family_market" bypass the window whitelist -- their semantics
        # come from the certified family's own replay code, not from session brackets. They
        # are executed by run_family_sleeves(), which is LOG-ONLY until the human creates
        # data/GENERIC_EXEC_ENABLED (arming stays a person's act; wiring does not wait for it).
        if s.get("exec") == "family_market":
            sleeves.append({"name": s["name"], "symbol": s["symbol"],
                            "family": s.get("family"), "selector": s.get("selector"),
                            "side": s.get("side", "LONG"), "state": s.get("state"),
                            "risk_frac": s.get("risk_frac"), "exec": "family_market",
                            "lot": "auto_ramp", "status": "LIVE"})
            continue
        # SCALP SLEEVES (principal 2026-09-04: every promotion candidate goes live, automatically).
        # The promoter writes the scalp lane's exact recipe -- timeframe, family, session and the
        # ATR geometry the forward clock replayed -- and run_scalp_sleeves() executes precisely
        # that through mt5desk/scalp_exec.py. Same arm switch as the family lane.
        if s.get("exec") == "scalp_market":
            sleeves.append({"name": s["name"], "symbol": s["symbol"],
                            "timeframe": s.get("timeframe"), "family": s.get("family"),
                            "session": s.get("session", "all"),
                            "stop_atr": s.get("stop_atr"), "target_atr": s.get("target_atr"),
                            "max_hold": s.get("max_hold"),
                            "risk_frac": s.get("risk_frac"), "exec": "scalp_market",
                            "lot": "auto_ramp", "status": "LIVE"})
            continue
        if s.get("window") not in {w[0] for w in GOLD_WINDOWS}:
            continue  # only validated window semantics
        sleeves.append({"name": s["name"], "symbol": s["symbol"],
                        "window": s["window"],
                        "sig_hour": next(w[1] for w in GOLD_WINDOWS if w[0] == s["window"]),
                        "rng": next(w[2] for w in GOLD_WINDOWS if w[0] == s["window"]),
                        # THE CONDITIONING STATE TRAVELS WITH THE SLEEVE, and before this it did
                        # not exist anywhere in the live chain. shadow_forward keyed on
                        # (symbol, window), promoter wrote no state field, and this function
                        # rebuilt every sleeve from `window` alone -- so a promoted
                        # "CADJPY asia FAILED_BREAK" would have traded CADJPY asia on EVERY day.
                        # The sleeve would carry the name of a validated strategy while running
                        # an unvalidated one (+0.163R unconditioned against the +0.276R that
                        # earned promotion), and nothing would have said so.
                        "state": s.get("state"),
                        "risk_frac": s.get("risk_frac"),
                        "lot": "auto_ramp", "status": "LIVE"})
    return sleeves, notes


def hibernated(sleeves: list[dict], regime_state: dict) -> set[str]:
    """Gateway names of sleeves flagged 'hibernate' in the regime monitor's state (writer:
    research/regime_monitor.py). Auto-kill: no new brackets until a human re-admits the sleeve
    (flag cleared or removed).

    Sleeve-key mapping: armed gold windows = 'XAUUSD|asia' etc; promoted sleeves use their
    ledger tag (symbol|window).
    """
    flags = regime_state.get("sleeves", {})
    killed = set()
    for s in sleeves:
        name = s["name"]
        key = f"XAUUSD|{name[5:]}" if name.startswith("gold_") else name.replace(".", "|")
        if flags.get(key, {}).get("flag") == "hibernate":
            killed.add(name)
    return killed


def state_allows(sleeve: dict, h1: pd.DataFrame, day: object) -> tuple[bool, str]:
    """May a state-conditioned sleeve trade today? FAILS CLOSED on any doubt.

    An unconditioned sleeve always passes. A conditioned one must have its state computable from
    the bars in hand AND match; if the state cannot be computed the sleeve does NOT trade, because
    the alternative is trading the unconditioned strategy under a conditioned sleeve's name and
    risk budget. Absence of a state is not permission.
    """
    want = sleeve.get("state")
    if not want:
        return True, ""
    try:
        from research.run_hunt12 import day_states
        got = day_states(h1).get(day)
    except Exception as exc:
        return False, f"state UNCOMPUTABLE ({type(exc).__name__}); refusing to trade unconditioned"
    if got is None:
        return False, "state unknown for today; refusing to trade unconditioned"
    return (got == want), (f"state {got} != {want}" if got != want else "")


# ------------------------------------------------------------------------------------ brackets

def h1_frame(rates: Any) -> pd.DataFrame:
    """Broker H1 rates (a MetaTrader5 structured array, or rows shaped like one) -> a UTC-indexed
    frame, exactly as the bracket loop has always built it: no casts, no synthetic columns."""
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.set_index("time").sort_index()


def day_range(h1: pd.DataFrame, rng: tuple | None, sig_hour: int) -> tuple[float, float] | None:
    """Range of the LAST calendar day: hours [0, sig_hour) if rng None else rng."""
    last_date = h1.index[-1].date()
    day = h1[h1.index.date == last_date]
    hours = day.index.hour.to_numpy()
    mask = hours < sig_hour if rng is None else (hours >= rng[0]) & (hours < rng[1])
    if not mask.any():
        return None
    return float(day["high"].to_numpy()[mask].max()), float(day["low"].to_numpy()[mask].min())


def atr_last(bars: pd.DataFrame, n: int = ATR_N) -> float:
    """Wilder-style ATR (EWM of true range) at the last bar, the way every bracket, veto record
    and stop ratchet on this desk has computed it -- one definition so they cannot drift."""
    tr = pd.concat([bars["high"] - bars["low"],
                    (bars["high"] - bars["close"].shift(1)).abs(),
                    (bars["low"] - bars["close"].shift(1)).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / n, min_periods=n).mean().iloc[-1])


def bracket_spec(hi: float, lo: float, a: float, tick: float, stops_level: int = 20) -> dict:
    """Build the bracket orders and their SL/TP as MT5 order fields."""
    span = hi - lo
    dist = max(1.2 * a, span)
    tick = max(tick, 0.01)
    # `int(...)` kept around `round`: research callers (replay_gateway) hand numpy scalars in,
    # and a numpy float's `round()` was not an `int` before NumPy 2. Points must be integers.
    sl_dist_pts = int(round(dist / tick)) + stops_level                        # noqa: RUF046
    tp_dist_pts = int(round(dist * RR / tick))                                 # noqa: RUF046
    return {
        "buy_stop": {"price": hi, "sl": hi - sl_dist_pts * tick,
                     "tp": hi + tp_dist_pts * tick},
        "sell_stop": {"price": lo, "sl": lo + sl_dist_pts * tick,
                      "tp": lo - tp_dist_pts * tick},
    }


def bracket_from_bars(df: pd.DataFrame, rng: tuple | None, sig_hour: int, tick_size: float,
                      stops_level: int) -> tuple[float, float, dict] | None:
    """(hi, lo, spec) for a session sleeve from its bars, or None while the range is not formed.

    THE ONE COMPUTATION the live bracket loop and the veto record share: the same `day_range`,
    the same ATR, the same `bracket_spec` on the same bars, so what the ledger says a vetoed
    sleeve WOULD have placed is exactly what the loop would have sent. The ATR floor of 5.0 is
    gold's: below it a quiet session's bracket would sit inside the noise of the next hour.
    """
    span = day_range(df, rng, sig_hour)
    if span is None:
        return None
    hi, lo = span
    a = atr_last(df)
    spec = bracket_spec(hi, lo, max(a, 5.0), tick_size, stops_level=stops_level)
    return hi, lo, spec


def diagnose(retcode: int | None, comment: str = "") -> str:
    """Turn a retcode into something an operator can act on."""
    if retcode is None:
        return "order_send returned nothing at all — the terminal connection is gone."
    if retcode in ACCEPTED_RETCODES:                  # placed / done
        return ""
    name, why = RETCODE_MEANING.get(
        retcode, (comment or "unrecognised", "not a retcode this desk has seen before; "
                  "look it up in the MT5 docs and add it to RETCODE_MEANING."))
    return f"{retcode} {name}: {why}"


def placement_verdict(orders: list[dict]) -> tuple[bool, bool, list[str]]:
    """(attempted, accepted, diagnoses) for one placement pass.

    UNAVAILABLE IS NOT REJECTED. A bracket the desk declined to send because price sat inside
    the broker's freeze band is the strategy having nothing to do today, not the venue refusing
    us. Counting it would pause the desk on exactly the days it correctly stood aside. The
    diagnoses are drawn from every order in the pass, as the pause file has always listed them.
    """
    attempted = [o for o in orders if not o.get("unavailable")]
    ok = [o for o in attempted if o.get("retcode") in ACCEPTED_RETCODES]
    diags = sorted({diagnose(o.get("retcode"), o.get("comment") or "")
                    for o in orders if diagnose(o.get("retcode"), o.get("comment") or "")})
    return bool(attempted), bool(ok), diags


def entry_is_legal(price: float, side: str, bid: float, ask: float,
                   point: float, stops_level: int) -> tuple[bool, str]:
    """Is this pending-order price far enough from market for the broker?

    THE CAUSE OF EVERY 10015 THIS DESK HAS SEEN. `bracket_spec` applies
    stops_level to the SL distance, which is a different constraint: a pending
    order is also rejected when its own ENTRY sits inside the stops/freeze band.
    A buy_stop must be at least stops_level points above the ask, a sell_stop
    the same below the bid.

    Session-range brackets hit this constantly, because the whole point of the
    strategy is to place the order AT the session extreme — and by the time the
    range is complete, price is frequently sitting right on it.

    Refusing here rather than pushing the price out is deliberate. Moving the
    entry to the nearest legal level would silently trade a different strategy:
    the edge was measured at the range boundary, not at the boundary plus
    whatever the broker's freeze distance happens to be today.
    """
    band = max(stops_level, 0) * max(point, 1e-9)
    if side == "buy_stop":
        gap = price - ask
        if gap < band:
            return False, (f"buy_stop {price:.2f} is {gap:.2f} above ask {ask:.2f}; "
                           f"broker needs {band:.2f}. Price is already at the range "
                           f"edge, so this bracket is NOT AVAILABLE today rather "
                           f"than available at a different level.")
        return True, ""
    gap = bid - price
    if gap < band:
        return False, (f"sell_stop {price:.2f} is {gap:.2f} below bid {bid:.2f}; "
                       f"broker needs {band:.2f}. NOT AVAILABLE today.")
    return True, ""


def bracket_deadline(sleeve: str, window: str | None = None,
                     now: datetime | None = None) -> datetime:
    """When this sleeve's bracket stops belonging to the session whose range formed it.

    "asian for asian, london for london, ny for ny" -- the principal, 2026-09-02.

    DERIVED FROM THE ARMED WINDOWS, NEVER A SECOND CONSTANT. Each window signals at its own hour
    and its trade belongs to the stretch before the next one opens; the last of the day ends at
    the force-close. From GOLD_WINDOWS (asia 07, london_am 13, afternoon 17) and CLOSE_HOUR 19.5:

        asia        07:00 -> 13:00   (6.0h, dies when London opens)
        london_am   13:00 -> 17:00   (4.0h, dies when the NY afternoon opens)
        afternoon   17:00 -> 19:30   (2.5h, dies at the force-close)

    A single flat TTL cannot express that, and six hours -- what a first pass used -- is right
    for asia alone: it would let a london_am bracket fire four hours into the afternoon session
    and an afternoon bracket outlive the force-close that exists to flatten the book. Deriving
    the deadline means adding a window changes this automatically and no second list can drift.

    An unrecognised window (a promoted family sleeve) takes BRACKET_TTL_HOURS as a ceiling --
    bounded, and by a number this docstring calls a fallback rather than a session.

    `now` is the placement clock; the wall clock when None.
    """
    now_utc = datetime.now(tz=UTC) if now is None else now
    win = window or (sleeve[len("gold_"):] if sleeve.startswith("gold_") else "")
    sig = next((float(w[1]) for w in GOLD_WINDOWS if w[0] == win), None)
    if sig is None:
        return now_utc + timedelta(hours=BRACKET_TTL_HOURS)
    later = [float(w[1]) for w in GOLD_WINDOWS if float(w[1]) > sig]
    end_hour = min(later) if later else float(CLOSE_HOUR)
    deadline = now_utc.replace(hour=int(end_hour), minute=round((end_hour % 1) * 60),
                               second=0, microsecond=0)
    if deadline <= now_utc:
        # Placed at or after its own session's end (a late or replayed pass). Never a deadline
        # in the past, and never more than the ceiling.
        deadline = min(now_utc + timedelta(hours=BRACKET_TTL_HOURS),
                       deadline + timedelta(days=1))
    return deadline


def sleeve_from_comment(comment: str, unattributed: str = "") -> str:
    """The sleeve a `DW<name>` order comment names; `unattributed` when the label did not
    survive the broker's round trip. Brokers do rewrite comments, so a caller that must record
    the fill regardless passes the marker it wants such a row to carry."""
    return comment[2:] if comment.startswith("DW") else (comment or unattributed)


def closed_trade_r(entry_price: float, sl_price: float, is_buy: bool, contract_size: float,
                   pl_quote: float) -> tuple[float, float]:
    """(risk_quote, r_multiple) for a closed deal: quote-currency P&L per lot over the
    entry-risk distance per lot (bracket SL distance x contract size in quote units).

    UNRECONSTRUCTIBLE IS RECORDED, NEVER GUESSED. Without both the entry and the stop there is
    no R multiple, and inventing one would put a fabricated number into the ledger the promoter
    uses to retire live sleeves (L1.28a): both come back as 0.0 and the caller stamps the row
    `r_unreconstructible`.
    """
    if entry_price <= 0 or sl_price <= 0:
        risk_quote = 0.0
    else:
        risk_quote = (entry_price - sl_price if is_buy else sl_price - entry_price)
    risk_per_lot = max(risk_quote, 0.0) * contract_size
    r = pl_quote / risk_per_lot if risk_per_lot > 0 else 0.0
    return risk_quote, r


# --------------------------------------------------------------------- execution context and gate

def exec_context(symbol: str, side: int, entry_ref: float, tick: object, dist: float,
                 g: object, lot: float = 0.0, *, hour: int | None = None):
    """The one Context both execution competitions price: same quote, stop, edge and lot.

    `tick` is anything with `bid`/`ask` (a live tick, or nothing -- then the spread is zero);
    `g` is the signal or plan, read for `atr_frac` and `edge_r` when it carries them. `hour` is
    the decision hour, the wall clock's when None.
    """
    from mt5desk.execution_policy import Context
    spread = float(getattr(tick, "ask", entry_ref) - getattr(tick, "bid", entry_ref))
    atr_frac = float(getattr(g, "atr_frac", 0.0) or dist / max(entry_ref, 1e-9))
    return Context(symbol=symbol, side=("buy" if side == 1 else "sell"),
                   quote=entry_ref, spread_frac=max(spread, 0.0) / max(entry_ref, 1e-9),
                   atr_frac=atr_frac, stop_frac=dist / max(entry_ref, 1e-9),
                   edge_r=float(getattr(g, "edge_r", 0.3) or 0.3),
                   hour=(datetime.now(tz=UTC).hour if hour is None else hour), lot=float(lot))


def release_gate(root: Path | None = None) -> tuple[bool, str]:
    """Whether this pass may open new risk, and why. Never raises: an identity that cannot be
    measured is a refusal with its reason, never an exception that takes the pass down.

    RELEASE IDENTITY (2026-09-05). The code this box runs must be the code that was sealed,
    tested and merged -- one SHA. When it is not (a stale checkout, a trampled module, a seal
    that never landed, an identity that cannot be measured), the gateway keeps managing what is
    open and opens NOTHING new. Unmeasured is not a licence, so every failure here is a `False`.
    """
    try:
        from mt5desk import release_identity
        ident = release_identity.verdict(root)      # writes data/release_identity.json
        return bool(ident.allows_new_risk()), str(ident.reason)
    except Exception as exc:
        return False, f"release_identity unavailable: {type(exc).__name__}: {exc}"


def ttl_expired(deadline: str | None, now_iso: str) -> bool:
    """Has a position's time exit passed? ISO strings compare as the executors have always
    compared them; no deadline means no exit is due."""
    return bool(deadline and now_iso >= deadline)


# ---------------------------------------------------------------------------- the family lane

@dataclass(frozen=True)
class FamilyStep:
    """What the family executor learned from one closed signal bar.

    `mark` says the bar has been CONSIDERED and must be recorded as such, whether or not it
    produced a signal, so the next pass does not re-run it; `note` is the log line's tail, or
    empty for a silent skip; `signal` is the family's Signal when there is one to trade.
    """

    mark: bool
    note: str = ""
    signal: object = None


def family_signal_hour(window: dict) -> int:
    """The hour a selector window signals at: its own `signal_at`, else its range start."""
    return window.get("signal_at") or window["range_start"]


def family_bar_due(closed: pd.DataFrame, sig_hour: int) -> pd.Timestamp | None:
    """The last CLOSED bar when it is the sleeve's signal bar, else None. The in-progress bar
    is excluded by the caller, exactly as the replay sees it.

    ONE DECISION PER DAY ON EVERY CHART, which `hour == sig_hour` alone only delivered on H1.
    An hour holds one H1 bar, twelve M5 bars and sixty M1 bars, so the bare hour test would have
    fired a sleeve certified to take ONE entry a day twelve or sixty times -- the same defect
    `family_calendar_month` had with its `hour == 0` test when the M1..D1 ladder landed, and the
    same correction: also require the bar to START the hour.

    H1 IS UNCHANGED BYTE FOR BYTE. Every H1 bar begins on the hour, so `minute == 0` is always
    true there and this test cannot alter a single existing decision. It is the sub-hourly charts
    that gain a rule they never had.

    WHY THE FIRST BAR OF THE HOUR AND NOT THE LAST. It preserves the H1 relationship exactly: the
    H1 bar labelled N closes at N+1:00 and the executor acts on it as the last closed bar, so the
    sleeve acts on the first bar whose label is the signal hour, as soon as that bar closes. On M5
    that is the N:00 bar acting at N:05 -- the same "act on the signal bar the moment it is
    final", one chart down.
    """
    last_bar = closed.index[-1]
    if last_bar.hour != sig_hour:
        return None
    return last_bar if last_bar.minute == 0 else None


def family_signal_step(closed: pd.DataFrame, last_bar: pd.Timestamp, *, last_signal_bar: object,
                       want_state: object, side: int, family_fn: Any,
                       day_states_fn: Any, call_params: dict | None = None) -> FamilyStep:
    """The replay-faithful signal decision for one family sleeve at its signal bar.

    FAITHFUL TO THE REPLAY OR NOT AT ALL: the signal comes from the SAME family function the
    forward clock replays, filtered to this bar and to the same day-state condition
    (`day_states_fn`, `run_hunt12.day_states`). A bar already considered is skipped without a
    mark; a state mismatch is marked and named; a failed signal computation is named and NOT
    marked, so the next pass tries again; no signal is marked silently.

    `call_params` SELECTS WHICH REPLAY, because the desk has two and they are different contracts
    rather than variants of one:

      None   the hunt16 call, `FAMILIES[fam](df, side)` -- positional, unparameterised, because a
             hunt16 cell takes its parameterisation from `WINDOWS[selector]` at sweep time. This
             is what `qquant_shadow` replays and what this function has always done, so passing
             nothing leaves every existing caller byte-identical.
      a dict the `mt5desk.families` / `families_orthogonal` call, which takes keyword params and a
             keyword side. `mt5desk.family_call` owns both shapes so this module and
             `shadow_forward` cannot drift; an EMPTY dict still selects this shape, and is the
             correct call for a price-only orthogonal family rather than a missing one.
    """
    if last_signal_bar == str(last_bar):
        return FamilyStep(mark=False)                          # this bar already considered
    if want_state:
        got = day_states_fn(closed).get(last_bar.date())
        if got != want_state:
            return FamilyStep(mark=True, note=f"no trade: day state {got} != {want_state}")
    try:
        from mt5desk.family_call import hunt16_signals, signals
        raw = (hunt16_signals(family_fn, closed, side) if call_params is None
               else signals(family_fn, closed, side=side, params=call_params))
        sigs = [g for g in raw if pd.Timestamp(g.time) == last_bar]
    except Exception as exc:
        return FamilyStep(mark=False,
                          note=f"FAMILY-EXEC signal computation failed ({exc}); skipped")
    if not sigs:
        return FamilyStep(mark=True)
    return FamilyStep(mark=True, signal=sigs[-1])


def family_entry(g: object, side: int, bid: float, ask: float) -> tuple[float, float]:
    """(entry reference, stop distance) for a family signal: market at the touch on the
    signal's side -- the engine's fill rule -- against the Signal's own absolute stop."""
    entry_ref = float(ask if side == 1 else bid)
    return entry_ref, abs(entry_ref - float(g.stop))


def family_ttl_until(last_bar: pd.Timestamp, ttl_bars: int, bar_minutes: int = 60) -> str:
    """The replay's time exit: `ttl_bars` BARS after the entry bar's open, as ISO text.

    BARS, NOT HOURS, and the distinction became real the day the executor learned M1..D1. This
    read `pd.Timedelta(hours=ttl_bars + 1)`, which is exactly right on H1 and wrong on every other
    chart: `engine.py` counts a signal's `ttl_bars` in INDEX POSITIONS (`for j in range(i, i +
    ttl)`), so twelve bars is twelve hours on H1, one hour on M5, and twelve DAYS on D1. An M5
    sleeve would have held its position twelve times too long and a D1 sleeve closed it
    twenty-four times too early -- in both cases a different strategy from the certified one,
    under the certified one's name, which is the defect class the family executor exists to refuse.

    `bar_minutes` DEFAULTS TO 60 so every existing H1 caller resolves to the identical timestamp
    it always has, including the `+ 1` -- the entry is at the open of the bar AFTER the signal
    bar, so the hold begins one bar later than `last_bar` and the offset counts from the signal.
    """
    return (last_bar + pd.Timedelta(minutes=(int(ttl_bars) + 1) * int(bar_minutes))).isoformat()


def family_order_desc(side: int, lot: float, symbol: str, g: object, ttl_until: str) -> str:
    """The order line the log carries, armed or not, so a shadow pass shows the exact order."""
    return (f"{'BUY' if side == 1 else 'SELL'} {lot} {symbol} @market"
            f" sl={float(g.stop):.5f} tp={float(g.target):.5f}"
            f" ttl_until={ttl_until}")


# ----------------------------------------------------------------------------- the scalp lane

def scalp_recipe(s: dict) -> tuple[str, str, float, float, int]:
    """(family, session, stop_atr, target_atr, max_hold) from a promoted scalp row, exactly as
    the promoter wrote them. An incomplete recipe raises (KeyError, TypeError, ValueError) for
    the executor to refuse with -- a lookalike trade under a certified sleeve's name is the
    defect class the family executor documents."""
    family, session = str(s["family"]), str(s.get("session") or "all")
    stop_atr, target_atr = float(s["stop_atr"]), float(s["target_atr"])
    max_hold = int(s["max_hold"])
    return family, session, stop_atr, target_atr, max_hold


def addon_entries(entries: list, price: float, per: float) -> list[tuple[float, float]]:
    """The basket's (price, lots) slices with one more added at `price`."""
    return [*[(float(p), float(u)) for p, u in entries], (price, per)]


def basket_lots(entries: list) -> float:
    """The basket's total lots, signed by nothing: the caller applies the side."""
    return sum(u for _, u in entries)


def basket_record(plan: Any, per: float, mode: str, target_atr: float) -> dict:
    """The state row for a freshly opened scalp basket: everything a later add-on needs."""
    return {"side": plan.side, "stop": float(plan.stop),
            "target": float(plan.target), "atr": float(plan.atr),
            "target_atr": target_atr, "mode": mode,
            "entries": [[plan.entry_ref, per]], "opened_bar": plan.bar_time}


def scalp_order_desc(plan: Any, per: float, symbol: str, mode: str) -> str:
    """The first slice's order line for the log."""
    return (f"{'BUY' if plan.side == 1 else 'SELL'} {per} {symbol} @market "
            f"sl={plan.stop:.5f} tp={plan.target:.5f} mode={mode} "
            f"ttl_until={plan.ttl_until}")


def addon_desc(side: int, per: float, symbol: str, stop: float, new_tp: float,
               depth: int) -> str:
    """An add-on slice's order line for the log."""
    return (f"ADD {'BUY' if side == 1 else 'SELL'} {per} {symbol} @market "
            f"sl={stop:.5f} tp->{new_tp:.5f} depth={depth}")
