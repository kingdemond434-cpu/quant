"""MT5 gateway for the research desk: multi-sleeve breakout engine, kill switches.

Modes:
  SHADOW (default): computes signals, NEVER sends orders.
  ARMED  (manual):  sends real bracket orders to the logged-in MT5 account.

Sleeves:
  - Gold book (armed, hunt5-validated, lot = auto_lot(equity), q=5.5%).
  - Promoted sleeves (data/sleeves.json, written ONLY by research/promoter.py):
    auto-promoted from shadow-forward verdicts at fixed 0.01 lot, auto-retired
    by the same promoter when forward evidence decays. The machine manages
    promoted sleeves; only the human arms the account (armed=true).

Housekeeping: cancel unfilled brackets 20:30 UTC, force-close positions 19:30
UTC (Friday too), never trade a closed market (stale-tick guard).

Deal ledger: every closed trade tagged with its sleeve (order comment) is
appended to data/live_ledger.jsonl for retire/champion logic.
"""

from __future__ import annotations

import json
import math
import time
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from mt5desk import position_manager as _pm  # noqa: E402
from mt5desk import provenance as _prov  # noqa: E402
from mt5desk.independence import measure_from_ledger  # noqa: E402
from mt5desk.config import desk_root, gateway_paused, terminal_path  # noqa: E402
from mt5desk.sizing import clamp_risk_frac, decay_factor  # noqa: E402

BASE = desk_root()
STATE = BASE / "data" / "gateway_state.json"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "gateway.log"
#: The pause flag `gateway_paused()` reads. Named here so the desk can set the
#: SAME file it already honours -- a second, private pause mechanism would be a
#: kill switch the operator does not know about.
PAUSED = BASE / "data" / "GATEWAY_PAUSED"

TERMINAL = terminal_path()
MAGIC = 341953

#: How far back record_trades looks for closed deals it has not yet written. Deals are deduped
#: by the venue's own ticket, so a wider window costs a list scan and cannot double-count. It
#: exists because the previous day-wide window silently lost every fill the gateway did not see
#: on the same calendar day: a skipped pass, an OOM kill or a restart after midnight left those
#: closes unrecorded permanently, since nothing ever looked backwards.
LEDGER_LOOKBACK_DAYS = 30

LOT = 0.02              # gold book lot; see Q_OPT below for the sizing policy
# RISK FRACTION OF EQUITY PER TRADE. Was 0.055, and that was not an arbitrary number: measured
# full Kelly on the 3-leg gold book (E[ln(1+qR)] maximised over the daily portfolio series,
# 5,728 trades, 2018-2026) is q* = 6.00%, so 5.5% was ~92% of Kelly, chosen deliberately.
#
# IT IS STILL WRONG, AND THE REASON IS NOT THE DRAWDOWN -- IT IS ESTIMATION FRAGILITY.
# Kelly is computed FROM the measured edge. That edge is in-sample, on one path, with params
# selected on this same gold data in hunt5. If the true expectancy is even half of the measured
# +0.159R/trade, then sizing at Kelly-on-measured is 2x over-levered, and past 2x Kelly the
# geometric growth rate turns NEGATIVE while every backtest number still looks excellent. Full
# Kelly is the point of maximum growth AND the point of maximum sensitivity to being wrong about
# the input; the whole margin of safety lives below it.
#
# The visible symptom is the drawdown ladder, in-sample, on the 3-leg book (worst -33.7R):
#     0.75% -> +118%/yr, -23.0% DD      <- here
#     1.04% -> +190%/yr, -30.7% DD      (what the 0.01 min lot forces at EUR1,684 -- see auto_lot)
#     3.00% -> +1,479%/yr, -68.4% DD    (half Kelly)
#     5.50% -> +7,660%/yr, -90.7% DD    (the old setting)
#     6.00% -> +9,816%/yr, -93.0% DD    (full Kelly)
# Those growth figures are in-sample and assume the edge is exactly as measured; they are the
# reason the ladder is shown, not a forecast. A -90% drawdown is also not survivable in practice
# regardless of what the geometric mean says about the path that produced it.
#
# THIS NUMBER MAY RISE, BUT ONLY ON FORWARD EVIDENCE. Fixed-fractional sizing already compounds
# -- auto_lot scales the lot with equity every run, so the book grows geometrically at a CONSTANT
# q without anyone touching this constant. Raising q is a separate claim: that the edge is better
# known than it is today. That claim is settled by live trades, not by backtest cells.

#: IMPORTED, NOT RESTATED. These used to be literals here AND in gateway_config_fallback.py, kept
#: in step by a test -- which duly caught the first drift, but only because someone had thought to
#: write it. Research code on Linux cannot import this module (MetaTrader5), so the fallback is
#: the one both sides can reach and is therefore the definition. Q_OPT is derived there from the
#: drawdown tolerance rather than chosen: 1.27%, the risk that spends exactly MAX_DRAWDOWN_
#: TOLERANCE over the book's worst -33.7R. See that module for the full argument.
from mt5desk.gateway_config_fallback import (  # noqa: E402
    BOOK_WORST_DD_R as _BOOK_WORST_DD_R,
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    MAX_DRAWDOWN_TOLERANCE,
    MAX_SLEEVE_HEAT_SHARE,
    Q_OPT,
)
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


def promoted_lot(equity: float, live_n: int, dist_usd: float | None = None,
                 symbol: str = GOLD_SYMBOL, info: object | None = None,
                 risk_frac: float | None = None,
                 decay_faded: object = None) -> float:
    """Dynamic lot for promoted sleeves: risk-fraction sizing x authority ramp.

    RISK BASE (principal order 2026-08-25): promoted sleeves target
    `clamp_risk_frac(risk_frac)` of equity per trade -- 3% base, dynamic-up to 10% only when
    the promoter records the economic justification in the sleeve row. THE RAMP MULTIPLIES THE
    RISK FRACTION, not the lot after the fact, so authority is expressed in equity terms:
    0.75% effective before 50 live trades (the same neighbourhood as the armed book's derived
    Q_OPT -- deliberate, per the estimation-fragility ladder above), 1.5% before 200, the full
    base only after 200 forward-proven live trades. A sleeve reaches 3% by EARNING it.

    `dist_usd` is the sleeve's own stop and is passed through for the same reason
    `auto_lot` takes it: a promoted sleeve on a wide session runs the same 2.8x
    overshoot as an armed one, and the ramp would have made it look deliberate.

    `symbol` IS THE SLEEVE'S OWN INSTRUMENT. Promoted sleeves are the ONLY non-gold things this
    gateway trades, so this function was the single place where gold's constants were guaranteed
    to be applied to something that is not gold. `sleeve_set` rewrites every promoted sleeve's
    lot field to "auto_ramp", so the literal 0.01 the promoter writes never reaches the venue and
    this path is always taken.
    """
    ramp = 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)
    # L1.59 FADE, OUTSIDE the clamp (gap-fixer 2026-08-29). `clamp_risk_frac` floors at 3%, so
    # the halved fraction `decay_monitor` wrote into data/sleeves.json was read straight back up
    # and a FADED sleeve sized identically to a healthy one -- measured, 3.0 lots vs 3.0 lots.
    # The flag is now the single source of truth and it is applied here, alongside `ramp`,
    # which is the same shape for the same reason: authority and decay both scale RISK, not the
    # lot after the fact. Reduce-only by construction; it can never raise a fraction.
    q_eff = clamp_risk_frac(risk_frac) * ramp * decay_factor(decay_faded)
    lot = auto_lot(equity, dist_usd, symbol, info, q=q_eff)
    # FLOOR, not nearest. Rounding up here reintroduced the overshoot `_lot_steps`
    # exists to prevent, on exactly the sleeves with the least forward evidence.
    lot = math.floor(lot / 0.01 + 1e-9) * 0.01
    return float(min(max(lot, 0.01), 5.0))


def sleeve_live_n(name: str) -> int:
    """Closed-trade count for a sleeve from the live ledger."""
    if not LEDGER.exists():
        return 0
    try:
        n = 0
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
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

# (label, signal_hour, range window)  range None => [0, signal_hour)
# ny_open QUARANTINED 2026-08-17: exp +0.029R, PF 1.05, maxDD -52.8R (rank 9).
# Must re-earn admission via a genuinely different conditioning rule.
GOLD_WINDOWS = [
    ("asia", 7, None),
    ("london_am", 13, (10, 13)),
    ("afternoon", 17, (14, 17)),
]


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
    from mt5desk import risk_units as _ru                      # noqa: PLC0415

    try:
        return _ru.eur_per_price_unit(symbol, info)             # type: ignore[arg-type]
    except _ru.RiskUnitUnmeasured:
        if symbol == GOLD_SYMBOL:
            return float(CONTRACT_OZ * FX_EUR)
        raise


#: EUR put at risk by the venue's smallest tradeable position on gold. Below the equity where
#: this equals Q_OPT, the FLOOR sets the risk and the policy does not -- deliberately kept, so a
#: small account can trade and compound up rather than being locked out, but never silently.
#:
#: STILL COMPUTED FROM THE LEGACY CONSTANTS, deliberately: it is a module-scope value and a
#: module-scope read of the live tick value would freeze at import for the life of the daemon
#: (L1.66). Callers that need the true figure ask `min_lot_risk_eur(symbol, dist)`.
MIN_LOT_RISK_EUR = 0.01 * DIST_USD * CONTRACT_OZ * FX_EUR   # ~17.57 (true gold figure ~16.51)


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


def stop_distance(spec: dict) -> float | None:
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


#: THE PORTFOLIO CAP IS `heat_budget()`, NOT A CONSTANT. A fixed `MAX_PORTFOLIO_HEAT = 0.04`
#: stood here and was already dead -- `cap_by_heat` consults `heat_budget(k_eff)` and nothing read
#: the constant -- but it stated 4% in the one place a reader looks for the budget, while the live
#: base is 3.81%. Two numbers, one of them decorative, is how a desk ends up sized by whichever
#: one the next person happens to find.
#:
#: WHY A BUDGET AND NOT A SLEEVE COUNT. Promoted sleeves take a fixed 0.01 lot -- 1.04% of equity
#: at EUR 1,684 -- and `load_sleeves()` returns every LIVE one. Ten promotions bracketing the same
#: morning is ~10% of the account at risk in one session. A COUNT cap would also let total risk
#: grow silently as equity FALLS, because the fixed floor becomes a larger fraction of a smaller
#: account: risk rising exactly when the account can least afford it. Per-sleeve risk control is
#: not risk control -- correlated sleeves fire together precisely in the regimes that hurt.

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


def allocator_heat() -> tuple[float | None, str]:
    """Total heat the E[log W] allocator resolved, or None with the reason it cannot be used.

    THE BUDGET IS AN OUTPUT, NOT A FORMULA. `heat_budget()` below derives a number from the
    drawdown tolerance and a breadth estimate, which was the best available answer while nothing
    solved for exposure. `research/pf_allocator.py` now does solve for it -- jointly with which
    sleeves hold it -- so when a fresh, certified, ARMED book exists it is the budget, and the
    derivation is what the desk falls back to when it does not.

    FAILS CLOSED ON EVERY DOUBT. Missing file, stale file, unparseable file, uncertified target,
    unarmed allocator: all return None, and the desk keeps running the derived budget it ran
    yesterday. Nothing here can RAISE heat by accident -- raising it takes a live artifact that
    passed its own certification plus a human-created arm file, which is the same shape as every
    other arming decision on this desk (GENERIC_EXEC_ENABLED, and gold re-arming).
    """
    try:
        if not (BASE / "data" / "PF_ALLOCATOR_ARMED").exists():
            return None, "allocator not armed (data/PF_ALLOCATOR_ARMED absent)"
        f = BASE / "reports" / "pf_allocation.json"
        if not f.exists():
            return None, "no pf_allocation.json"
        age = time.time() - f.stat().st_mtime
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
    except Exception as exc:                                    # noqa: BLE001
        return None, f"allocator artifact unreadable ({type(exc).__name__})"


def allocator_book() -> tuple[dict[str, float] | None, str]:
    """The optimiser's PER-SLEEVE target risk fractions, or None with the reason.

    THE BOOK WAS SOLVED AND THEN NOT USED. `allocator_heat` takes the optimiser's TOTAL and
    `allocator_order` takes its RANKING, and each sleeve was then sized by `q_charge` /
    `realised_q` / Q_OPT -- so the one number the optimiser actually solves for, h_i, reached
    nothing. A book of {A: 4.3%, B: 3.7%, C: 2.1%} became "total 10.1%, in that order", which is
    a different allocation to the one that maximised E[log W].

    AUTHORITY IS EARNED, NOT ASSUMED, and that is the whole reason this is a separate function
    from `allocator_heat`. A dynamic allocator sits above every edge and reallocates, so it can
    destroy compounding faster than any single sleeve. It may size positions only while a FRESH
    certificate says it beat equal-weight, inverse-vol, risk-parity and doing-nothing on the
    desk's own sampled worlds at equal heat. No certificate, a stale one, or a losing one all
    return None -- and None means the existing sizing path runs exactly as it does today.

    Every check `allocator_heat` makes still applies: armed, fresh, certified, finite growth.
    This adds the proof on top; it never substitutes for them.
    """
    total, why = allocator_heat()
    if total is None:
        return None, f"no allocator book: {why}"
    try:
        from libs.portfolio.allocator_proof import read_certificate
        cert, cwhy = read_certificate(BASE.parent.parent)
    except Exception as exc:                                    # noqa: BLE001
        return None, f"proof unreadable ({type(exc).__name__}: {exc})"
    if cert is None:
        return None, f"allocator may rank but not size: {cwhy}"
    try:
        art = json.loads((BASE / "reports" / "pf_allocation.json").read_text(encoding="utf-8"))
        book = {str(k): float(v) for k, v in (art.get("book") or {}).items() if float(v) > 0.0}
    except Exception as exc:                                    # noqa: BLE001
        return None, f"pf_allocation book unreadable ({type(exc).__name__})"
    if not book:
        # An EMPTY book is a real answer -- "hold nothing" -- but it is not a sizing instruction,
        # and returning {} here would read to the caller as "size everything at zero" rather than
        # "the allocator declined to allocate". The no-new-exposure path already handles that.
        return None, "allocator book is empty (no positive-heat sleeve)"
    drift = abs(sum(book.values()) - total)
    if drift > 0.005:
        # The book and the total come from the same artifact and must agree. A disagreement means
        # one of them was rewritten independently, and sizing on a book that does not sum to the
        # budget the heat cap enforces would over- or under-deploy silently.
        return None, f"book sums to {sum(book.values()):.4f}, heat says {total:.4f}"
    return book, f"allocator book authoritative ({len(book)} sleeve(s)); {cwhy}"


def allocator_order(sleeves: list[dict]) -> list[dict]:
    """Reorder `sleeves` by marginal dE[log W], best first; unpriced sleeves keep their place.

    WHAT THIS REPLACES. `cap_by_heat` trims in list order and `sleeve_set()` emits gold first, so
    the armed gold book was senior to everything else by position. The stated justification was
    that gold is "the one book with forward evidence behind it" -- which stopped being true once
    the forward clocks filled, and a seniority rule that outlives its reason silently becomes a
    rule that the oldest sleeve wins. Ordering by what each sleeve is worth to the book makes the
    trim drop the cheapest growth rather than the newest name.

    SILENT ON ABSENCE, NEVER WRONG ON IT: no artifact, or a stale one, and the caller's order
    stands unchanged.
    """
    try:
        f = BASE / "reports" / "pf_allocation.json"
        if not f.exists() or time.time() - f.stat().st_mtime > _ALLOC_MAX_AGE_S:
            return sleeves
        mg = json.loads(f.read_text(encoding="utf-8")).get("marginal_delta_elog") or {}
        if not isinstance(mg, dict) or not mg:
            return sleeves
        rank = {str(k): float(v) for k, v in mg.items()}
    except Exception:                                           # noqa: BLE001
        return sleeves
    known = [s for s in sleeves if str(s.get("name")) in rank]
    unknown = [s for s in sleeves if str(s.get("name")) not in rank]
    known.sort(key=lambda s: -rank[str(s["name"])])
    # Unknown sleeves go LAST, not first: a sleeve the allocator has never priced has no claim
    # on the budget ahead of one it has measured and valued.
    return known + unknown


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
    # SOLVED AGAINST THE DRAWDOWN TARGET, not read off a constant -- and it is THE SAME q the
    # desk actually sizes each trade at, because Q_OPT is now that same derivation rather than a
    # hardcoded second opinion. One tolerance, one formula, both levels: the budget can no longer
    # be spending a drawdown allowance that per-trade sizing has privately decided against.
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
    if k_eff is None or not (k_eff == k_eff) or k_eff < 1.0:
        return float(min(base, MAX_HEAT_CEILING))
    # More independent bets survive more total heat at the SAME drawdown: portfolio drawdown for
    # N sleeves at heat H scales roughly as H/sqrt(k_eff), so holding drawdown fixed lets H grow
    # with sqrt(k_eff). Breadth is paid for with measured orthogonality.
    scaled = base * math.sqrt(float(k_eff) / _HEAT_BASE_KEFF)
    return float(min(max(scaled, base), MAX_HEAT_CEILING))


def load_sleeves() -> list[dict]:
    """Promoted sleeves from data/sleeves.json (writer: research/promoter.py)."""
    if not SLEEVES_FILE.exists():
        return []
    try:
        data = json.loads(SLEEVES_FILE.read_text(encoding="utf-8"))
        return [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
    except Exception:
        return []


def cap_by_heat(sleeves: list[dict], equity: float,
                per_sleeve_q: float | None = None,
                k_eff: float | None = None) -> tuple[list[dict], str | None]:
    """Trim `sleeves` so their combined risk stays inside MAX_PORTFOLIO_HEAT.

    Returns the admitted sleeves and a note when anything was dropped, because a silently
    shortened book is indistinguishable from a book that had nothing to trade.

    ORDER IS BY MARGINAL dE[log W], not by the caller's list position. It used to be the latter,
    justified by `sleeve_set()` emitting gold first: "a cap that dropped sleeves arbitrarily could
    silently retire the one book with forward evidence behind it in favour of three that have
    none." That was true when gold was the only sleeve with forward evidence and stopped being
    true when the forward clocks filled -- at which point a seniority rule with a dead reason is
    just a rule that the oldest sleeve wins, and the desk cannot displace a worse edge with a
    better one. `allocator_order` ranks by what each sleeve contributes; absent an allocator
    artifact the caller's order still stands, so the old behaviour is the fallback, not the rule.

    EACH SLEEVE IS CHARGED ITS OWN q, NOT THE BOOK'S. This multiplied ONE q -- gold's, because
    `realised_q` defaulted to gold's contract economics -- by the sleeve COUNT, so a book of
    heterogeneous instruments was capped as though every leg cost what a gold leg costs. The two
    errors compounded: the sizing path put a JPY cross on 5.90x its budget, and this function
    then billed that sleeve at gold's 0.98%, so three of them read as a 2.94% book against a true
    22.2%. A cap that cannot see what a leg actually costs is not a cap.
    """
    if equity <= 0 or not sleeves:
        return list(sleeves), None
    # THE ALLOCATOR'S BOOK IS THE BUDGET WHEN THERE IS ONE. `heat_budget` is the derivation the
    # desk falls back to; `allocator_heat` is a number something actually solved for. Fails
    # closed to the derivation on any doubt, so this cannot raise heat by accident.
    solved, why = allocator_heat()
    budget_src = why if solved is not None else f"derived (allocator unusable: {why})"
    # ORDERED BY WHAT EACH SLEEVE IS WORTH, not by where the caller put it. See allocator_order.
    sleeves = allocator_order(sleeves)
    # Per-sleeve q: an explicit scalar override still applies to every sleeve (that is what a
    # caller asking for one means), otherwise each sleeve is priced on ITS OWN instrument.
    qs: list[float] = []
    for s in sleeves:
        if per_sleeve_q is not None:
            qs.append(float(per_sleeve_q))
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
        except Exception:                                       # noqa: BLE001
            # UNMEASURABLE IS CHARGED AT THE MOST EXPENSIVE MEASURED LEG, never at gold's by
            # default. An instrument whose risk cannot be priced must not be the cheapest thing
            # in the book (L1.28a); if nothing at all is measurable the budget admits nobody.
            qs.append(float("nan"))
    known = [q for q in qs if q == q and q > 0]
    fallback = max(known) if known else 0.0
    budget = solved if solved is not None else heat_budget(k_eff)
    qs = [(q if q == q and q > 0 else fallback) for q in qs]
    if fallback <= 0:
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


def regime_hibernate(sleeves: list[dict]) -> set[str]:
    """Gateway names of sleeves flagged 'hibernate' in data/regime_state.json
    (writer: research/regime_monitor.py). Auto-kill: no new brackets until a
    human re-admits the sleeve (flag cleared or removed).

    Sleeve-key mapping: armed gold windows = 'XAUUSD|asia' etc; promoted
    sleeves use their ledger tag (symbol|window).
    """
    p = BASE / "data" / "regime_state.json"
    if not p.exists():
        return set()
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    flags = state.get("sleeves", {})
    killed = set()
    for s in sleeves:
        name = s["name"]
        key = f"XAUUSD|{name[5:]}" if name.startswith("gold_") else name.replace(".", "|")
        if flags.get(key, {}).get("flag") == "hibernate":
            killed.add(name)
    return killed


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"{now()} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def load_state() -> dict:
    defaults = {"armed": False, "brackets": {}, "position": None,
                "last_bracket_date": None, "last_reconcile": None}
    if STATE.exists():
        st = json.loads(STATE.read_text(encoding="utf-8"))
        for k, v in defaults.items():
            st.setdefault(k, v)
        return st
    return defaults


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")


def connect() -> bool:
    if mt5.terminal_info() is not None:
        return True
    if not mt5.initialize(path=TERMINAL):
        log(f"mt5 initialize failed: {mt5.last_error()}")
        return False
    return True


def day_range(h1: pd.DataFrame, rng: tuple | None, sig_hour: int) -> tuple[float, float] | None:
    """Range of the LAST calendar day: hours [0, sig_hour) if rng None else rng."""
    last_date = h1.index[-1].date()
    day = h1[h1.index.date == last_date]
    hours = day.index.hour.to_numpy()
    if rng is None:
        mask = hours < sig_hour
    else:
        mask = (hours >= rng[0]) & (hours < rng[1])
    if not mask.any():
        return None
    return float(day["high"].to_numpy()[mask].max()), float(day["low"].to_numpy()[mask].min())


def bracket_spec(hi: float, lo: float, a: float, tick: float, stops_level: int = 20) -> dict:
    """Build the bracket orders and their SL/TP as MT5 order fields."""
    span = hi - lo
    dist = max(1.2 * a, span)
    tick = max(tick, 0.01)
    sl_dist_pts = int(round(dist / tick)) + stops_level
    tp_dist_pts = int(round(dist * RR / tick))
    return {
        "buy_stop": {"price": hi, "sl": hi - sl_dist_pts * tick,
                     "tp": hi + tp_dist_pts * tick},
        "sell_stop": {"price": lo, "sl": lo + sl_dist_pts * tick,
                      "tp": lo - tp_dist_pts * tick},
    }


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


def diagnose(retcode: int | None, comment: str = "") -> str:
    """Turn a retcode into something an operator can act on."""
    if retcode is None:
        return "order_send returned nothing at all — the terminal connection is gone."
    if retcode in (10008, 10009):                     # placed / done
        return ""
    name, why = RETCODE_MEANING.get(
        retcode, (comment or "unrecognised", "not a retcode this desk has seen before; "
                  "look it up in the MT5 docs and add it to RETCODE_MEANING."))
    return f"{retcode} {name}: {why}"


def note_placement(st: dict, sleeve: str, orders: list) -> bool:
    """Record whether a placement pass succeeded, and PAUSE THE DESK if none do.

    THE DEFECT THIS EXISTS TO END. `place_bracket` logged each rejection and
    returned; nothing counted them, nothing escalated, nothing stopped. The
    gateway ran for four days with 100% of its orders refused -- every sleeve,
    both sides, 10015 and 10017 -- writing retcodes into a state file and trying
    again tomorrow. Total failure and a quiet market produced the same silence,
    which is the absence-read-as-permission pattern in its purest form: nothing
    checked for SUCCESS, so nothing could tell them apart.

    Returns True while the desk is still healthy enough to keep going.
    """
    # UNAVAILABLE IS NOT REJECTED. A bracket the desk declined to send because
    # price sat inside the broker's freeze band is the strategy having nothing
    # to do today, not the venue refusing us. Counting it would pause the desk
    # on exactly the days it correctly stood aside.
    attempted = [o for o in orders if not o.get("unavailable")]
    ok = [o for o in attempted if o.get("retcode") in (10008, 10009)]
    hist = st.setdefault("placement_health", {"consecutive_total_rejections": 0,
                                              "last_ok": None, "last_error": None})
    if not attempted:
        return True
    if ok:
        hist["consecutive_total_rejections"] = 0
        hist["last_ok"] = now()
        return True

    hist["consecutive_total_rejections"] += 1
    diags = sorted({diagnose(o.get("retcode"), o.get("comment") or "")
                    for o in orders if diagnose(o.get("retcode"), o.get("comment") or "")})
    hist["last_error"] = {"time": now(), "sleeve": sleeve, "diagnoses": diags}
    n = hist["consecutive_total_rejections"]
    log(f"PLACEMENT FAILED ENTIRELY [{sleeve}] -- {n} consecutive pass(es) with no "
        f"accepted order")
    for d in diags:
        log(f"    {d}")
    if n < MAX_TOTAL_REJECTIONS:
        return True

    # PAUSE, not just shout. A desk nobody is watching that logs an error and
    # keeps going is a desk that discovers the problem when someone happens to
    # read a file. The pause is the same file the operator uses by hand, so
    # clearing it is one command and the reason is written where they will look.
    PAUSED.parent.mkdir(parents=True, exist_ok=True)
    PAUSED.write_text(
        f"AUTO-PAUSED {now()}: {n} consecutive placement passes with ZERO accepted "
        f"orders.\n\n" + "\n".join(f"  {d}" for d in diags) +
        f"\n\nNothing has traded. Fix the cause, then delete this file to re-arm.\n",
        encoding="utf-8")
    log("GATEWAY AUTO-PAUSED: no order has been accepted in "
        f"{n} consecutive passes. Nothing is trading; the reason is in "
        f"{PAUSED}. This is deliberate -- a desk whose orders are all refused is "
        "not a desk with a quiet market.")
    return False


def margin_ok(symbol: str, lot: float, price: float) -> bool:
    """Skip a sleeve if margin would be tight (machine kill switch)."""
    acc = mt5.account_info()
    if acc is None or acc.margin_free <= 0:
        return False
    need = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot, price)
    if need is None:
        return True  # cannot compute; let broker decide
    return need <= acc.margin_free * 0.9


#: Placement intents, one line per pending order sent. Separate from the deal ledger because the
#: two are written at different moments by different events -- an intent exists the instant an
#: order is sent, a deal only when it closes, and most intents never become deals at all (the
#: 20:30 cancel). Keeping them apart means an unfilled bracket is recorded as what it is rather
#: than inferred from an absence.
INTENTS = BASE / "data" / "order_intents.jsonl"


def _record_intent(**row) -> None:
    """Append one placement intent. NEVER raises -- telemetry must not break the money path."""
    try:
        row["time"] = now()
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception as exc:                      # noqa: BLE001
        log(f"intent record failed (non-fatal): {type(exc).__name__}: {exc}")


def place_bracket(st: dict, spec: dict, sleeve: str, symbol: str, lot: float) -> dict:
    if not st["armed"]:
        log(f"SHADOW [{sleeve}] would place bracket: {json.dumps(spec, default=str)}")
        return {"shadow": True, "orders": []}
    sent = []
    # Current market, read ONCE for the legality check below. A pending order
    # whose entry sits inside the broker's freeze band is refused with 10015,
    # and finding that out from the broker costs a rejection that then looks
    # like a failing desk rather than an unavailable setup.
    _t = mt5.symbol_info_tick(symbol)
    _si = mt5.symbol_info(symbol)
    _point = float(getattr(_si, "point", 0.01) or 0.01)
    _lvl = int(getattr(_si, "trade_stops_level", 0) or 0)

    for side in ("buy_stop", "sell_stop"):
        s = spec[side]
        if _t is not None and _lvl > 0:
            legal, why_illegal = entry_is_legal(
                float(s["price"]), side, float(_t.bid), float(_t.ask), _point, _lvl)
            if not legal:
                log(f"NOT AVAILABLE [{sleeve}] {side}: {why_illegal}")
                # Recorded as UNAVAILABLE, which is a different fact from a
                # rejected order and must not count toward the rejection
                # escalation -- a desk pausing itself because the market sat on
                # the range edge would be a desk that stops working on exactly
                # the days its strategy has nothing to do.
                sent.append({"side": side, "retcode": None, "unavailable": True,
                             "comment": why_illegal})
                continue
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY_STOP if side == "buy_stop" else mt5.ORDER_TYPE_SELL_STOP,
            "price": s["price"],
            "sl": s["sl"],
            "tp": s["tp"],
            # BROKER-SIDE EXPIRY, so the TTL survives this process dying. A gateway-side sweep
            # only runs while the gateway runs, and an OOM kill or a box restart would leave a
            # stale bracket resting at the broker indefinitely -- exposure nothing is managing.
            # `_expiry_request` falls back to GTC when the symbol refuses timed orders, and the
            # sweep below is what covers that case.
            **_expiry_request(symbol, sleeve, spec.get("window")),
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "deviation": 20,
            "magic": MAGIC,
            "comment": f"DW{sleeve}",
        }
        res = mt5.order_send(req)
        code = res.retcode if res else None
        why = diagnose(code, getattr(res, "comment", "") or "")
        if why:
            log(f"ORDER FAILED [{sleeve}] {side}: {why}")
        # THE INTENT, RECORDED AT PLACEMENT. Without this line slippage is unknowable: once the
        # order fills, MT5 reports only the price it GOT, and the price the desk ASKED for is
        # gone. Every backtest number on this desk assumes fills at exactly `s["price"]`, and
        # nothing has ever checked that assumption -- the crypto desk made the same omission and
        # discovered its real execution cost was 50x its modelled one, on trades that needed
        # twelve days of funding to repay a single entry. Written at send time, joined by ticket
        # in `markout.py` when the deal closes.
        _record_intent(sleeve=sleeve, symbol=symbol, side=side, lot=lot,
                       intended=float(s["price"]), sl=float(s["sl"]), tp=float(s["tp"]),
                       ticket=(getattr(res, "order", None) if res else None), retcode=code)
        sent.append({"side": side, "retcode": code,
                     "comment": res.comment if res else None})
        log(f"ORDER [{sleeve}] {side} -> retcode={code} "
            f"{res.comment if res else ''}")
    # THE SUCCESS CHECK. Without it a pass where every order was refused is
    # indistinguishable from a quiet day, which is how four days of total
    # rejection passed unnoticed.
    note_placement(st, sleeve, sent)
    return {"shadow": False, "orders": sent}


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


def bracket_deadline(sleeve: str, window: str | None = None) -> datetime:
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
    """
    now_utc = datetime.now(tz=UTC)
    win = window or (sleeve[len("gold_"):] if sleeve.startswith("gold_") else "")
    sig = next((float(w[1]) for w in GOLD_WINDOWS if w[0] == win), None)
    if sig is None:
        return now_utc + timedelta(hours=BRACKET_TTL_HOURS)
    later = [float(w[1]) for w in GOLD_WINDOWS if float(w[1]) > sig]
    end_hour = min(later) if later else float(CLOSE_HOUR)
    deadline = now_utc.replace(hour=int(end_hour), minute=int(round((end_hour % 1) * 60)),
                               second=0, microsecond=0)
    if deadline <= now_utc:
        # Placed at or after its own session's end (a late or replayed pass). Never a deadline
        # in the past, and never more than the ceiling.
        deadline = min(now_utc + timedelta(hours=BRACKET_TTL_HOURS),
                       deadline + timedelta(days=1))
    return deadline


def _expiry_request(symbol: str, sleeve: str = "", window: str | None = None) -> dict:
    """`type_time`/`expiration` fields for a bracket, or GTC when the symbol refuses timed orders.

    MT5 exposes what a symbol accepts through `symbol_info().expiration_mode`; a symbol without
    the SPECIFIED bit rejects the whole order if one is sent, so this asks first rather than
    losing the bracket. Absence of the information falls back to GTC and the gateway-side sweep,
    never to an unbounded order the desk believes is bounded.
    """
    try:
        info = mt5.symbol_info(symbol)
        mode = int(getattr(info, "expiration_mode", 0) or 0)
        if info is not None and (mode & mt5.SYMBOL_EXPIRATION_SPECIFIED):
            until = bracket_deadline(sleeve, window)
            return {"type_time": mt5.ORDER_TIME_SPECIFIED,
                    "expiration": int(until.timestamp())}
    except Exception as exc:                                    # noqa: BLE001
        log(f"{symbol}: expiration mode unreadable ({type(exc).__name__}); bracket is GTC "
            f"and relies on the {BRACKET_TTL_HOURS:.0f}h sweep")
    return {"type_time": mt5.ORDER_TIME_GTC}


def expire_stale_brackets(st: dict) -> int:
    """Cancel this desk's pending orders whose SESSION has ended. Returns how many.

    THE SWEEP IS NOT REDUNDANT WITH THE BROKER EXPIRY. It covers the symbols whose expiration
    mode refuses a timed order, brackets placed before this TTL existed, and anything left
    resting by a gateway that died between placing and cancelling. It is keyed on MAGIC, so it
    can only ever touch orders this desk placed.
    """
    try:
        orders = mt5.orders_get() or ()
    except Exception as exc:                                    # noqa: BLE001
        log(f"TTL sweep skipped: orders_get failed ({type(exc).__name__})")
        return 0
    killed = 0
    now_utc = datetime.now(tz=UTC)
    for o in orders:
        if int(getattr(o, "magic", 0) or 0) != MAGIC:
            continue
        setup = getattr(o, "time_setup", None)
        if not setup:
            continue
        placed = datetime.fromtimestamp(int(setup), tz=UTC)
        # THE SAME PER-SESSION RULE THE ORDER WAS PLACED UNDER, recovered from its own label, so
        # the sweep and the broker expiry can never disagree. A flat cutoff here would defeat the
        # point: it would keep an afternoon bracket alive hours past the force-close the broker
        # had already been told to kill it at.
        comment = str(getattr(o, "comment", "") or "")
        sleeve = comment[2:] if comment.startswith("DW") else ""
        if bracket_deadline(sleeve) > now_utc and placed.date() == now_utc.date():
            continue
        res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
        gone = not any(getattr(x, "ticket", None) == o.ticket
                       for x in (mt5.orders_get(symbol=o.symbol) or ()))
        if gone:
            killed += 1
            log(f"TTL: cancelled {o.symbol} order {o.ticket} placed {placed:%H:%M} "
                f"({(datetime.now(tz=UTC) - placed).total_seconds() / 3600:.1f}h old, "
                f"limit {BRACKET_TTL_HOURS:.0f}h)")
        else:
            log(f"TTL: {o.symbol} order {o.ticket} SURVIVED cancellation "
                f"(retcode {getattr(res, 'retcode', None)}); it is still resting")
    return killed


def cancel_pending(st: dict, symbol: str) -> None:
    """Remove unfilled pending orders, and PROVE each one is gone.

    THIS NEVER WORKED ONCE. It called `mt5.order_delete(ticket)`, and the MetaTrader5 Python
    package HAS NO SUCH FUNCTION -- verified against the live terminal 2026-09-01:
    `hasattr(mt5, "order_delete")` is False. Removal is documented as order_send() with
    TRADE_ACTION_REMOVE (=8). So every call raised AttributeError while the very next line
    logged "cancelled pending ticket <n>", and unfilled buy/sell stops were left standing on a
    live account with the desk reporting them cancelled.

    IT ALSO TOOK THE REST OF THE PASS WITH IT. Neither this function nor its caller caught the
    exception, and the housekeeping block runs at hour >= CANCEL_HOUR (20:30 UTC) BEFORE
    close_positions, record_trades and reconcile. From 20:30 onward, every one of those was
    skipped -- which is the shape of `last_reconcile` standing at 2026-08-17 and of a live
    ledger that never appeared.

    SO CANCELLATION IS NOW IDEMPOTENT AND VERIFIED, not hopeful: send the documented removal,
    read the retcode, then re-read orders_get and confirm the ticket is ABSENT. A ticket that
    survives is reported as still live rather than logged as cancelled, because a cancellation
    the desk believes in but the venue did not perform is worse than a loud failure. One
    ticket's failure never aborts the others, and never the pass.
    """
    if not st["armed"]:
        log("SHADOW would cancel unfilled brackets")
        return
    pending = list(mt5.orders_get(symbol=symbol) or [])
    if not pending:
        return
    for o in pending:
        ticket = getattr(o, "ticket", None)
        try:
            res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        # Broad on purpose: one bad ticket must not strand the others, nor abort the pass.
        except Exception as exc:
            log(f"CANCEL FAILED ticket {ticket} ({symbol}): "
                f"{type(exc).__name__}: {exc}; order may still be live")
            continue
        retcode = getattr(res, "retcode", None)
        # THE VENUE IS THE STATE, not the return value. A retcode can be optimistic, a result can
        # be None on a dropped connection, and either way the only fact that matters is whether
        # the ticket is still accepting a fill.
        still = any(getattr(x, "ticket", None) == ticket
                    for x in (mt5.orders_get(symbol=symbol) or []))
        if still:
            log(f"CANCEL NOT CONFIRMED ticket {ticket} ({symbol}): retcode={retcode}, "
                f"order STILL PRESENT after remove -- treat as live")
            continue
        log(f"cancelled pending ticket {ticket} ({symbol}) retcode={retcode}, "
            f"confirmed absent from orders_get")


def close_positions(st: dict, symbol: str) -> None:
    if not st["armed"]:
        log("SHADOW would force-close open positions")
        return
    for p in mt5.positions_get(symbol=symbol) or []:
        tick = mt5.symbol_info_tick(symbol)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": MAGIC,
        }
        res = mt5.order_send(req)
        log(f"CLOSE ticket {p.ticket} ({symbol}) -> retcode={res.retcode if res else None} "
            f"{res.comment if res else ''}")


#: Minimum improvement, in R, before a stop modification is worth sending. A modify costs a
#: round trip to the broker and a chance of rejection; nudging a stop by a fraction of a tick
#: every pass spends both for nothing. Expressed in R rather than price so it means the same
#: thing on gold and on EURUSD.
MIN_RATCHET_IMPROVEMENT_R = 0.05


def _original_stop_distance(st: dict, ticket: int, price_open: float, sl: float) -> float | None:
    """The stop distance this position was OPENED with, captured once and then remembered.

    R is defined against the INITIAL risk. Once management starts moving the stop, the live
    `sl` no longer encodes it, so the distance has to be captured while it still does -- the
    first time this ticket is seen -- and reused thereafter.

    THE RESTART HAZARD IS REAL AND IS LOGGED RATHER THAN HIDDEN. If `data/gateway_state.json`
    is lost while a managed position is open, first sight after the restart captures the ALREADY
    MOVED stop and every subsequent R for that ticket is computed against a smaller denominator,
    overstating the multiple. The capture is therefore logged loudly on the pass it happens, so
    a capture appearing for a position that is not brand new is visible as the anomaly it is.
    A position with no stop at all returns None and is left alone: there is no initial risk to
    ratchet against, and inventing one would be inventing the denominator of every number that
    follows.
    """
    if not sl:
        return None
    store = st.setdefault("orig_stop_dist", {})
    key = str(ticket)
    if key not in store:
        dist = abs(price_open - sl)
        if dist <= 0:
            return None
        store[key] = dist
        log(f"MANAGE capture: ticket {ticket} initial stop distance {dist:.5f} "
            f"(open {price_open:.5f} sl {sl:.5f}) -- expected only on a position's first pass")
    return float(store[key])


def manage_open_positions(st: dict, sleeves: list[dict]) -> None:
    """Ratchet the stop on every open position. SHADOW UNLESS `st["armed"]`.

    THE GAP THIS CLOSES. `engine.py` models a trailing, banking runner and every backtest
    expectancy on this desk is computed with it applied; this gateway placed a stop at entry and
    never touched it again. The two were different strategies and the difference was the whole
    right tail -- a live winner could round-trip to its opening stop, an outcome the backtest
    would never have shown because there the stop had moved.

    THE BROKER IS THE STATE. `p.sl` is re-read from `positions_get` on every pass and fed in as
    the current stop, so a rejected modify simply leaves the next pass re-proposing against the
    unchanged level. Nothing is cached that could disagree with the account, which is what makes
    this idempotent and acknowledgement-driven rather than merely hopeful.
    """
    symbols = list({s["symbol"] for s in sleeves} | {"XAUUSD"})
    for symbol in symbols:
        positions = mt5.positions_get(symbol=symbol) or []
        if not positions:
            continue
        info = mt5.symbol_info(symbol)
        if info is None:
            log(f"MANAGE {symbol}: no symbol_info; skipped")
            continue
        for p in positions:
            side = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            dist = _original_stop_distance(st, p.ticket, p.price_open, p.sl)
            if dist is None:
                log(f"MANAGE ticket {p.ticket} ({symbol}): no stop on the position; "
                    f"nothing to ratchet against and none invented")
                continue

            # Bars SINCE ENTRY only. A pre-entry extreme is a level the thesis never reached.
            since = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1,
                                         datetime.fromtimestamp(p.time, tz=UTC),
                                         datetime.now(tz=UTC))
            if since is None or len(since) < 2:
                log(f"MANAGE ticket {p.ticket} ({symbol}): fewer than 2 bars since entry; "
                    f"too early to locate an extreme")
                continue
            bars = pd.DataFrame(since)

            # ATR on a longer window than the holding period, because a young position has too
            # few bars of its own to characterise volatility with.
            h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 400)
            if h1 is None or len(h1) < ATR_N + 1:
                log(f"MANAGE ticket {p.ticket} ({symbol}): ATR unavailable; skipped")
                continue
            hd = pd.DataFrame(h1)
            tr = pd.concat(
                [hd["high"] - hd["low"],
                 (hd["high"] - hd["close"].shift(1)).abs(),
                 (hd["low"] - hd["close"].shift(1)).abs()], axis=1).max(axis=1)
            atr = float(tr.ewm(alpha=1 / ATR_N, min_periods=ATR_N).mean().iloc[-1])
            if not (atr > 0):
                log(f"MANAGE ticket {p.ticket} ({symbol}): ATR non-positive; skipped")
                continue

            extreme, stall = _pm.extreme_and_stall(
                highs=[float(x) for x in bars["high"]],
                lows=[float(x) for x in bars["low"]], side=side)
            decision = _pm.ratchet(
                entry=float(p.price_open), current_stop=float(p.sl), stop_distance=dist,
                extreme=extreme, atr=atr, side=side, bars_since_extreme=stall)

            tag = f"MANAGE ticket {p.ticket} ({symbol})"
            if not decision.moves:
                log(f"{tag}: {decision.reason}")
                continue
            if decision.improvement_r < MIN_RATCHET_IMPROVEMENT_R:
                log(f"{tag}: improvement {decision.improvement_r:+.3f}R below the "
                    f"{MIN_RATCHET_IMPROVEMENT_R:.2f}R floor; not worth a modify")
                continue

            # THE VENUE'S OWN MINIMUM DISTANCE. A stop inside stops_level is rejected, and a
            # rejection every pass is a management loop that looks busy and protects nothing.
            stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
            tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
            tick_now = mt5.symbol_info_tick(symbol)
            if stops_level and tick_size and tick_now is not None:
                ref = tick_now.bid if side == 1 else tick_now.ask
                if abs(ref - decision.new_stop) < stops_level * tick_size:
                    log(f"{tag}: proposed stop {decision.new_stop:.5f} is inside the venue's "
                        f"{stops_level}-point stops level; held")
                    continue

            if not st["armed"]:
                log(f"SHADOW would modify {tag}: sl {p.sl:.5f} -> {decision.new_stop:.5f} "
                    f"| {decision.reason}")
                continue

            res = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": p.ticket,
                "sl": decision.new_stop,
                "tp": p.tp,
                "magic": MAGIC,
            })
            rc = res.retcode if res else None
            log(f"{tag}: MODIFY sl {p.sl:.5f} -> {decision.new_stop:.5f} "
                f"(protected {decision.protected_r_before:+.3f}R -> "
                f"{decision.protected_r_after:+.3f}R) retcode={rc} "
                f"{diagnose(rc, res.comment if res else '')}")

            # CONFIRM FROM THE BROKER, not from the return code. A retcode is an answer about
            # the request; the position is the answer about the account.
            after = mt5.positions_get(ticket=p.ticket) or []
            if after:
                got = float(after[0].sl)
                if abs(got - decision.new_stop) > (tick_size or 1e-9):
                    log(f"{tag}: WARNING requested sl {decision.new_stop:.5f} but the broker "
                        f"reports {got:.5f} -- next pass re-proposes against what it reports")


def reconcile(st: dict) -> dict:
    pos = []
    pend = []
    for symbol in list({s["symbol"] for s in load_sleeves()}) + ["XAUUSD"]:
        pos += mt5.positions_get(symbol=symbol) or []
        pend += mt5.orders_get(symbol=symbol) or []
    st["position"] = [
        {"ticket": p.ticket, "type": p.type, "volume": p.volume,
         "price_open": p.price_open, "sl": p.sl, "tp": p.tp,
         "profit": p.profit, "symbol": p.symbol} for p in pos
    ] if pos else None
    st["pending"] = [{"ticket": o.ticket, "type": o.type, "price": o.price_open,
                      "symbol": o.symbol} for o in pend] if pend else None
    st["last_reconcile"] = now()
    return st


def _position_context(deal: object) -> tuple[float, float, float, str]:
    """(entry price, stop, take-profit, comment) for the position a closing deal belongs to.

    MT5 splits what this desk needs across two record types and joins them only on
    `position_id`: the DEAL holds the executed price and P&L, the ORDER holds the stop and
    target. A closing deal therefore knows what it made and not what it risked, and R is the
    ratio of the two -- so both must be fetched.

    RETURNS ZEROS RATHER THAN RAISING. A single unreadable position must not abort the loop that
    records every other fill: that is exactly how one AttributeError kept the entire live ledger
    empty while the account carried real P&L.
    """
    pid = getattr(deal, "position_id", None)
    if not pid:
        return 0.0, 0.0, 0.0, ""
    entry = sl = tp = 0.0
    comment = ""
    try:
        for o in (mt5.history_orders_get(position=pid) or ()):
            if not comment:
                comment = str(getattr(o, "comment", "") or "")
            if float(getattr(o, "sl", 0.0) or 0.0) > 0:
                sl = float(o.sl)
                tp = float(getattr(o, "tp", 0.0) or 0.0)
        for x in (mt5.history_deals_get(position=pid) or ()):
            if getattr(x, "entry", None) == mt5.DEAL_ENTRY_IN:
                entry = float(getattr(x, "price", 0.0) or 0.0)
                break
    except Exception as exc:                                    # noqa: BLE001
        log(f"position {pid}: context unreadable ({type(exc).__name__}); R left unmeasured")
        return 0.0, 0.0, 0.0, comment
    return entry, sl, tp, comment


def record_trades(st: dict, sleeves: list[dict]) -> None:
    """Append closed trades (deal OUT with DW comment) to the live ledger.

    r_multiple: quote-currency P&L per lot / entry-risk distance per lot
    (entry risk = bracket SL distance x contract size in quote units).
    """
    if not st["armed"]:
        return

    # ALREADY-RECORDED DEALS, so the window below can be widened without duplicating rows.
    # The ledger is append-only JSONL and `deal` is the venue's own ticket, unique per fill.
    seen_deals: set = set()
    if LEDGER.exists():
        try:
            for line in LEDGER.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                with contextlib.suppress(ValueError):
                    tid = json.loads(line).get("deal")
                    if tid is not None:
                        seen_deals.add(tid)
        except OSError:
            seen_deals = set()

    try:
        # A DAY-WIDE WINDOW LOSES EVERY FILL THE GATEWAY DID NOT SEE THE SAME DAY. Any pass that
        # is skipped, OOM-killed or started after midnight left that day's closes unrecorded
        # forever, because nothing ever looked backwards. Dedupe by deal ticket makes a wider
        # window free, so the lookback is bounded by history rather than by uptime.
        since = datetime.now(tz=UTC) - timedelta(days=LEDGER_LOOKBACK_DAYS)
        deals = mt5.history_deals_get(since, datetime.now(tz=UTC), magic=MAGIC) or []
    except Exception:
        return
    written = 0
    for d in deals:
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        if getattr(d, "ticket", None) in seen_deals:
            continue
        # A DEAL CARRIES NO STOP, NO TAKE-PROFIT AND NO ENTRY PRICE, and this function read all
        # three off it. MEASURED 2026-09-02 on the live box: every pass raised
        # `AttributeError("'TradeDeal' object has no attribute 'price_open'")` and the whole
        # trade loop aborted, so `live_ledger.jsonl` was never written -- the file whose absence
        # was diagnosed on 2026-09-01 as a comment-prefix problem and fixed there. That fix was
        # necessary and not sufficient: the function could not run at all.
        #
        # MT5's own shapes: TradeDeal has {price, position_id, order, entry, profit, commission,
        # swap, volume}; TradeOrder has {price_open, sl, tp}. So the risk this trade actually
        # took is reconstructed from the position's OPENING deal (entry price) and its ORDER
        # (stop), joined on position_id -- the only join MT5 offers between the two.
        entry_price, sl_price, tp_price, order_comment = _position_context(d)
        comment = (d.comment or order_comment or "")
        # MAGIC IS THE IDENTITY, NOT THE COMMENT. history_deals_get already filtered to
        # magic=MAGIC, so every deal here is this gateway's own; requiring the comment to ALSO
        # start with "DW" made a broker-side rewrite silently discard the entire ledger. Brokers
        # do rewrite comments -- it is the same lesson the EA learned when it stopped trusting
        # them for idempotency and moved to a persistent journal. Measured 2026-09-01:
        # live_ledger.jsonl did not exist on either box while the account carried real P&L and
        # open margin, so matched_fills read 0 and execution was UNMEASURED. A fill this desk
        # placed is now recorded whether or not its label survived the round trip; the sleeve
        # name is taken from the comment when it is there and marked unattributed when it is not,
        # which is a recoverable gap, unlike never recording the fill at all.
        sleeve = comment[2:] if comment.startswith("DW") else (comment or "UNATTRIBUTED")
        sym_info = mt5.symbol_info(d.symbol)
        if sym_info is None:
            continue
        # risk per lot at entry: SL distance x contract (quote units)
        pl_quote = float(d.profit) + float(d.commission or 0.0) + float(d.swap or 0.0)
        if entry_price <= 0 or sl_price <= 0:
            # UNRECONSTRUCTIBLE IS RECORDED, NEVER GUESSED. Without both the entry and the stop
            # there is no R multiple, and inventing one would put a fabricated number into the
            # ledger the promoter uses to retire live sleeves (L1.28a).
            risk_quote = 0.0
        else:
            risk_quote = (entry_price - sl_price if d.type == mt5.POSITION_TYPE_BUY
                          else sl_price - entry_price)
        risk_per_lot = max(risk_quote, 0.0) * sym_info.trade_contract_size
        r = pl_quote / risk_per_lot if risk_per_lot > 0 else 0.0
        rec = {"time": now(), "sleeve": sleeve, "symbol": d.symbol,
               "side": d.type, "pl_quote": round(pl_quote, 2),
               "r_multiple": round(r, 4), "volume": d.volume,
               "commission": d.commission, "swap": d.swap, "deal": d.ticket,
               # THE FILL, so it can be compared with the intent. price_open was already read
               # here to size `risk_quote` and then thrown away, which is why no markout was
               # possible: the one number that reveals execution quality was computed and
               # discarded on every single trade. contract_size travels with it so slippage can
               # be converted to account currency without a second lookup at analysis time.
               "fill_price": float(d.price), "entry_price": float(entry_price),
               "sl": float(sl_price), "tp": float(tp_price),
               "r_unreconstructible": bool(entry_price <= 0 or sl_price <= 0),
               "order": getattr(d, "order", None),
               "contract_size": float(sym_info.trade_contract_size),
               "risk_quote": round(float(risk_quote), 6),
               # WHICH ACCOUNT TRADED. The broker is switched by editing one line of
               # data/terminal_path.txt, so the account under this gateway can change between two
               # runs. Without these fields a Fusion DEMO fill lands in the same ledger the
               # promoter reads to RETIRE a live sleeve, indistinguishable forever after -- and a
               # newly funded live account would be judged partly on demo history sitting above it
               # in the same file. Demo fills are not a conservative approximation of live ones:
               # a demo server fills stops at the trigger with no slippage, which is exactly the
               # assumption markout exists to test.
               **_prov.stamp(_prov.current_account(mt5.account_info()))}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        written += 1
    if written:
        log(f"ledger: recorded {written} closed trade(s)")


def ledger_rows() -> list[dict]:
    """Closed trades recorded by this desk. Torn final lines are skipped, never fatal."""
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
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


#: Written by research/promoter.py when a gold window trips a retire rule. Read on every pass so
#: a retirement takes effect within one gateway cycle rather than waiting for a restart.
GOLD_RETIRED_FILE = BASE / "data" / "GOLD_RETIRED.json"


def _load_retired_gold() -> dict:
    """Retired gold windows, or {} when the file is absent/unreadable.

    FAILS OPEN ON PURPOSE, and this is the one place in the gateway where that is right: an
    unreadable file must not silently stop a live book that is otherwise trading correctly.
    A retirement that does not apply is visible in the next promoter run and in this log line;
    a book that stops because a JSON file got truncated is an outage with no author.
    """
    try:
        v = json.loads(GOLD_RETIRED_FILE.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def sleeve_set() -> list[dict]:
    """All active sleeves: gold book + promoted, with window metadata."""
    sleeves = []
    # THE GOLD BOOK DECAYS LIKE EVERYTHING ELSE NOW (principal, 2026-09-01). research/promoter.py
    # walks these three names against the same retire rules it applies to promoted sleeves and
    # writes the loser here with its reason. Until 2026-09-01 the armed gold book was exempt from
    # retirement entirely -- so the desk's ONLY live sleeves were the only ones with no automatic
    # decay protection, because the retire rules walked sleeves.json, which is empty.
    # ABSENT FILE = NOTHING RETIRED, which is the behaviour up to now; and re-arming stays a
    # person's act, because undoing a retirement means deleting the entry by hand.
    retired_gold = _load_retired_gold()
    for label, sig_hour, rng in GOLD_WINDOWS:
        name = f"gold_{label}"
        if name in retired_gold:
            log(f"GOLD {name}: RETIRED ({retired_gold[name].get('reason', 'no reason recorded')}); "
                f"not emitted this pass")
            continue
        sleeves.append({"name": name, "symbol": "XAUUSD",
                        "window": label, "sig_hour": sig_hour, "rng": rng,
                        "lot": "auto", "status": "LIVE"})
    for s in load_sleeves():
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
    return sleeves


def state_allows(sleeve: dict, h1: "pd.DataFrame", day: object) -> tuple[bool, str]:
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
        from research.run_hunt12 import day_states           # noqa: PLC0415
        got = day_states(h1).get(day)
    except Exception as exc:                                  # noqa: BLE001
        return False, f"state UNCOMPUTABLE ({type(exc).__name__}); refusing to trade unconditioned"
    if got is None:
        return False, "state unknown for today; refusing to trade unconditioned"
    return (got == want), (f"state {got} != {want}" if got != want else "")


#: The one-file arm switch for generic family execution. ABSENT = every family sleeve logs the
#: exact order it would place and places nothing; the operator watches it be right, then
#: `type nul > data\GENERIC_EXEC_ENABLED` is the deliberate human act that arms the lane.
GENERIC_EXEC_ENABLED = BASE / "data" / "GENERIC_EXEC_ENABLED"


def run_family_sleeves(st: dict, sleeves: list[dict], equity: float) -> None:
    """Execute hunt-certified family sleeves with replay-faithful semantics (GAP 124).

    FAITHFUL TO THE REPLAY OR NOT AT ALL: signals come from the SAME
    `run_hunt16.FAMILIES[family]` code the forward clock replays, filtered to the same
    selector hour and day-state condition; entry is market at the open following the signal
    bar (the engine's fill rule); sl/tp are the Signal's own absolute levels; TTL closes the
    position `ttl_bars` hours after entry. Anything this function cannot compute exactly is a
    loud skip, never an approximation -- trading a lookalike strategy under a certified
    sleeve's name is the defect class `state_allows` documents.
    """
    fam_sleeves = [s for s in sleeves if s.get("exec") == "family_market"]
    if not fam_sleeves:
        return
    try:
        from research.run_hunt12 import day_states                # noqa: PLC0415
        from research.run_hunt16 import FAMILIES, WINDOWS         # noqa: PLC0415
    except Exception as exc:                                      # noqa: BLE001
        log(f"FAMILY-EXEC unavailable ({type(exc).__name__}: {exc}); "
            f"{len(fam_sleeves)} certified sleeve(s) NOT traded this pass")
        return
    armed = bool(st.get("armed")) and GENERIC_EXEC_ENABLED.exists()
    gstate = st.setdefault("generic", {})
    now_utc = datetime.now(tz=UTC)
    for s in fam_sleeves:
        name, family, selector = s["name"], s.get("family"), s.get("selector")
        side = 1 if str(s.get("side", "LONG")).upper() == "LONG" else -1
        if family not in FAMILIES or selector not in WINDOWS:
            log(f"[{name}] FAMILY-EXEC refused: family/selector has no exact executable")
            continue
        sig_hour = WINDOWS[selector].get("signal_at") or WINDOWS[selector]["range_start"]
        h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)
        if h1 is None or len(h1) < 60:
            log(f"[{name}] FAMILY-EXEC: bars unavailable; skipped")
            continue
        df = pd.DataFrame(h1)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        # The last CLOSED bar: current in-progress bar is excluded, exactly as replay sees it.
        closed = df.iloc[:-1]
        last_bar = closed.index[-1]
        if last_bar.hour != sig_hour:
            continue
        srec = gstate.setdefault(name, {})
        if srec.get("last_signal_bar") == str(last_bar):
            continue                                   # this bar already considered
        want_state = s.get("state")
        if want_state:
            got = day_states(closed).get(last_bar.date())
            if got != want_state:
                srec["last_signal_bar"] = str(last_bar)
                log(f"[{name}] no trade: day state {got} != {want_state}")
                continue
        try:
            sigs = [g for g in FAMILIES[family](closed, side)
                    if pd.Timestamp(g.time) == last_bar]
        except Exception as exc:                                  # noqa: BLE001
            log(f"[{name}] FAMILY-EXEC signal computation failed ({exc}); skipped")
            continue
        srec["last_signal_bar"] = str(last_bar)
        if not sigs:
            continue
        g = sigs[-1]
        tick = mt5.symbol_info_tick(s["symbol"])
        sym = mt5.symbol_info(s["symbol"])
        if tick is None or sym is None:
            log(f"[{name}] FAMILY-EXEC: no tick/symbol_info; skipped")
            continue
        entry_ref = float(tick.ask if side == 1 else tick.bid)
        dist = abs(entry_ref - float(g.stop))
        if not (dist > 0):
            log(f"[{name}] FAMILY-EXEC: degenerate stop distance; skipped")
            continue
        try:
            lot = promoted_lot(equity, sleeve_live_n(name), dist, s["symbol"], sym,
                               s.get("risk_frac"), s.get("decay_faded"))
        except Exception as exc:                                  # noqa: BLE001
            log(f"[{name}] FAMILY-EXEC: cannot price risk ({exc}); skipped")
            continue
        ttl_until = (last_bar + pd.Timedelta(hours=int(g.ttl_bars) + 1)).isoformat()
        order_desc = (f"{'BUY' if side == 1 else 'SELL'} {lot} {s['symbol']} @market"
                      f" sl={float(g.stop):.5f} tp={float(g.target):.5f}"
                      f" ttl_until={ttl_until}")
        if not armed:
            log(f"[{name}] WOULD PLACE (generic exec "
                f"{'not armed' if st.get('armed') else 'account unarmed'}; "
                f"enable={GENERIC_EXEC_ENABLED.name}): {order_desc}")
            continue
        if not margin_ok(s["symbol"], lot, entry_ref):
            log(f"[{name}] FAMILY-EXEC SKIPPED: margin tight (lot={lot})")
            continue
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": s["symbol"], "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if side == 1 else mt5.ORDER_TYPE_SELL,
            "price": entry_ref, "sl": float(g.stop), "tp": float(g.target),
            "deviation": 20, "magic": MAGIC, "comment": f"DW{name}"[:31],
        })
        rc = res.retcode if res else None
        _record_intent(sleeve=name, symbol=s["symbol"],
                       side=("buy" if side == 1 else "sell"), lot=lot,
                       intended=entry_ref, sl=float(g.stop), tp=float(g.target),
                       ticket=(getattr(res, "order", None) if res else None), retcode=rc)
        log(f"[{name}] FAMILY-EXEC ORDER -> retcode={rc} {diagnose(rc, getattr(res, 'comment', '') or '')} "
            f"| {order_desc}")
        if rc in (10008, 10009):
            srec["open_ttl_until"] = ttl_until
    # TTL housekeeping: positions past their deadline are closed regardless of P&L -- the
    # replay's ttl exit is part of the certified strategy, not an optional tidy-up.
    for s in fam_sleeves:
        srec = gstate.get(s["name"]) or {}
        deadline = srec.get("open_ttl_until")
        if deadline and now_utc.isoformat() >= deadline:
            if st.get("armed") and GENERIC_EXEC_ENABLED.exists():
                close_positions(st, s["symbol"])
            else:
                log(f"[{s['name']}] SHADOW would TTL-close open position(s)")
            srec.pop("open_ttl_until", None)


def main() -> None:
    if gateway_paused():
        log("gateway paused (data/GATEWAY_PAUSED present); no trading this pass")
        return
    if not connect():
        return
    st = load_state()
    tick = mt5.symbol_info_tick("XAUUSD")
    if tick is None:
        log("no tick; market likely closed")
        mt5.shutdown()
        return
    equity = float(mt5.account_info().equity)
    st["equity"] = round(equity, 2)

    tnow = pd.Timestamp(tick.time, unit="s", tz="UTC")
    today = tnow.date()
    hour = tnow.hour + tnow.minute / 60.0
    day_key = str(today)

    # stale tick (weekend/holiday/terminal dead): never trade a closed market
    age_sec = (datetime.now(tz=UTC) - tnow).total_seconds()
    if age_sec > 1800:
        st = reconcile(st)
        save_state(st)
        log(f"idle: tick stale {age_sec/60:.0f} min (last {tnow}); market closed")
        mt5.shutdown()
        return

    if st["last_bracket_date"] != day_key:
        st["brackets"] = {}
        st["last_bracket_date"] = day_key
        save_state(st)

    sleeves = sleeve_set()

    # MANAGE WHAT IS ALREADY OPEN BEFORE CONSIDERING ANYTHING NEW, and run it on EVERY pass --
    # before the regime filter, before the equity floor, before heat. Those gates decide whether
    # to OPEN a position; a position that is already on carries risk regardless of whether the
    # desk would enter it again today, and hibernating a sleeve must not orphan its open trade.
    # Shadow unless st["armed"]: unarmed passes log the modification they would have sent.
    try:
        manage_open_positions(st, sleeves)
    except Exception as exc:                                        # noqa: BLE001
        # Never let management take the gateway down. A desk that cannot ratchet a stop is
        # degraded; a desk that cannot place or reconcile anything because management raised is
        # broken, and the second is strictly worse than the first.
        log(f"MANAGE FAILED (positions left untouched): {type(exc).__name__}: {exc}")
    save_state(st)

    reg_killed = regime_hibernate(sleeves)
    if reg_killed:
        log(f"REGIME: auto-hibernate, no new brackets: {reg_killed}")
        sleeves = [s for s in sleeves if s["name"] not in reg_killed]
    if equity < PROMOTED_MIN_EQUITY:
        sleeves = [s for s in sleeves if s["name"].startswith("gold_")]
        if load_sleeves():
            log(f"equity {equity:.0f} < {PROMOTED_MIN_EQUITY:.0f}: promoted sleeves dormant")
    # AGGREGATE HEAT, applied after every other filter so it sees the sleeves that would really
    # trade. Deferred sleeves are named in the log rather than dropped quietly.
    #
    # k_eff IS MEASURED AND PASSED, and until now it was neither. `cap_by_heat(sleeves, equity)`
    # supplied no breadth term, so `heat_budget` returned its base 3.81% on every call and the
    # whole sqrt(k_eff) ladder was dead code -- the book pinned to a three-leg budget however many
    # independent edges it went on to earn. That is a permanent cap on compounding, which is the
    # opposite of what the budget was written to do: breadth is meant to be PAID FOR with measured
    # orthogonality and then spent.
    #
    # The estimate is deliberately conservative in three ways, because an overstated k_eff feeds
    # straight into leverage: correlations are computed on overlapping days only (never zero
    # filled), the 95% UPPER bound on mean correlation is used rather than the point estimate, and
    # an unmeasurable book returns None, which routes back to the base budget rather than to the
    # ceiling.
    # CURRENCY CONCENTRATION BINDS THE BUDGET TOO, from the positions actually open.
    #
    # Return correlation is backward-looking and estimated on the quiet sample: four sleeves each
    # secretly SHORT USD measure as four independent bets for as long as the dollar does not move,
    # and then move together on the day it does. `libs/risk/fx_factors` decomposes a book into its
    # currency legs and reported `n_effective 1.019 across 17 sleeves` on the live survivor set --
    # seventeen positions behaving as one bet. It had ZERO non-test callers.
    #
    # EXPOSURES COME FROM OPEN POSITIONS, NOT FROM THE SLEEVE ROSTER, and the distinction is not
    # pedantry: a session bracket places a buy stop AND a sell stop, so its direction does not
    # exist until one of them fills. Reading intent off the roster would assume a sign the desk
    # has not taken, and could tighten the budget against a book that is genuinely two-sided.
    # A flat book has nothing to concentrate and so correctly constrains nothing.
    _exposure: dict[str, float] = {}
    try:
        for _p in mt5.positions_get() or []:
            _sgn = 1.0 if int(getattr(_p, "type", 0)) == 0 else -1.0
            _exposure[str(_p.symbol)] = _exposure.get(str(_p.symbol), 0.0) + _sgn * float(
                getattr(_p, "volume", 0.0) or 0.0)
    except Exception as _exc:                                        # noqa: BLE001
        # A breadth MEASUREMENT must never stop the trading loop. An unreadable position list
        # leaves exposures empty, which leaves the budget exactly as the return series set it.
        log(f"factor breadth: positions unreadable ({type(_exc).__name__}: {_exc}); "
            f"return breadth alone")
    k_eff, k_why = measure_from_ledger(
        ledger_rows(), _prov.current_account(mt5.account_info()),
        exposures=_exposure or None)
    log(k_why)
    # Read ONCE per pass: the book is an artifact, and re-reading it per sleeve could size two
    # legs of the same pass from two different solves if the allocator rewrote it mid-loop.
    _book, _book_why = allocator_book()
    log(f"sizing: {_book_why}")
    # EACH SLEEVE'S LAST REAL STOP, so the cap prices legs on what they actually traded rather
    # than on a house average. The gateway already records every bracket it places; not reading
    # them back meant the one number that decides how much heat a leg costs was the only number
    # the cap did not have.
    for _s in sleeves:
        _spec = (st.get("brackets", {}).get(_s["name"]) or {}).get("spec")
        _d = stop_distance(_spec) if _spec else None
        if _d:
            _s["dist"] = _d
        # A risk_frac sleeve is BILLED its own effective fraction (base x ramp), not the house
        # Q_OPT -- undercharging heat for the very sleeves running above Q_OPT would recreate
        # the 2.94%-believed/22.2%-true defect documented on cap_by_heat.
        # THE OPTIMISER'S OWN FRACTION, WHEN IT HAS EARNED THE RIGHT TO SET IT. h_i is what
        # maximised E[log W] jointly with every other sleeve; Q_OPT and the ramp are what the
        # desk falls back to when nothing solved for it. Only reachable behind a fresh proof
        # certificate (see `allocator_book`), so an unproven allocator cannot resize the book.
        if _book is not None and _s["name"] in _book:
            _s["risk_frac"] = float(_book[_s["name"]])
            _s["sized_by"] = "allocator_book"
        elif _s.get("lot") == "auto_ramp":
            _ramp = 0.25 if sleeve_live_n(_s["name"]) < 50 else (
                0.5 if sleeve_live_n(_s["name"]) < 200 else 1.0)
            _s["q_charge"] = (clamp_risk_frac(_s.get("risk_frac")) * _ramp
                              * decay_factor(_s.get("decay_faded")))
    sleeves, heat_note = cap_by_heat(sleeves, equity, k_eff=k_eff)
    if heat_note:
        log(heat_note)
    # Hunt-certified family sleeves run their own replay-faithful executor -- AFTER the heat
    # cap, so an inadmissible sleeve never reaches it, and OUTSIDE the bracket loop, whose
    # session-window semantics they do not share.
    try:
        run_family_sleeves(st, sleeves, equity)
    except Exception as exc:                                        # noqa: BLE001
        log(f"FAMILY-EXEC FAILED (bracket path unaffected): {type(exc).__name__}: {exc}")
    save_state(st)
    if st["last_bracket_date"] == day_key:
        for s in sleeves:
            if s.get("exec") == "family_market":
                continue
            if st["brackets"].get(s["name"]):
                continue
            if hour < s["sig_hour"]:
                continue
            sym = mt5.symbol_info(s["symbol"])
            if sym is None:
                continue
            h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)
            if h1 is None:
                log(f"copy_rates failed {s['symbol']}: {mt5.last_error()}")
                continue
            df = pd.DataFrame(h1)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("time").sort_index()
            # THE STATE GATE, applied before any bracket is computed. A conditioned sleeve that
            # cannot confirm its state does not trade -- see `state_allows`.
            ok_state, why_state = state_allows(s, df, datetime.now(tz=UTC).date())
            if not ok_state:
                log(f"[{s['name']}] no trade today: {why_state}")
                continue
            rng2 = day_range(df, s["rng"], s["sig_hour"])
            if rng2 is None:
                log(f"[{s['name']}] range not ready at {hour:.1f}")
                continue
            hi, lo = rng2
            tr = pd.concat(
                [df["high"] - df["low"],
                 (df["high"] - df["close"].shift(1)).abs(),
                 (df["low"] - df["close"].shift(1)).abs()], axis=1
            ).max(axis=1)
            a = float(tr.ewm(alpha=1 / ATR_N, min_periods=ATR_N).mean().iloc[-1])
            spec = bracket_spec(hi, lo, max(a, 5.0), sym.trade_tick_size,
                                stops_level=int(getattr(sym, "trade_stops_level", 0) or 20))
            # SIZE AGAINST THIS SLEEVE'S OWN STOP, which `spec` holds one line above.
            # Sizing from the house DIST_USD while the real bracket was in hand made every
            # wide-session sleeve trade 2.5-2.8x its budget -- see `auto_lot`.
            dist = stop_distance(spec)
            if dist is None:
                log(f"[{s['name']}] SKIPPED: bracket spec has no usable stop distance; "
                    f"refusing to size from the house average")
                continue
            # SIZE IN THIS SLEEVE'S OWN INSTRUMENT, from the LIVE symbol_info already in hand.
            # `sym` carries trade_tick_value, which is what the venue will actually credit for
            # one tick in the account currency at today's FX -- the quantity `CONTRACT_OZ *
            # FX_EUR` was a frozen stand-in for. A sleeve whose risk cannot be priced does not
            # trade, for the same reason a sleeve with no usable stop does not.
            try:
                lot = auto_lot(equity, dist, s["symbol"], sym) if s["lot"] == "auto" else (
                    promoted_lot(equity, sleeve_live_n(s["name"]), dist, s["symbol"], sym,
                                 s.get("risk_frac"), s.get("decay_faded"))
                    if s["lot"] == "auto_ramp" else float(s["lot"]))
                q_real = realised_q(equity, dist, s["symbol"], sym, lot=lot)
            except Exception as exc:                              # noqa: BLE001
                log(f"[{s['name']}] SKIPPED: cannot price {s['symbol']} risk in account "
                    f"currency ({exc}); refusing to size from the house average")
                continue
            log(f"[{s['name']}] stop {dist:.5g} -> lot {lot:.2f} "
                f"(realised q {q_real:.2%})")
            # margin guard (machine kill switch): skip sleeve if tight
            if not margin_ok(s["symbol"], lot, max(hi, lo)):
                log(f"[{s['name']}] SKIPPED: margin tight (lot={lot})")
                st["brackets"][s["name"]] = {"date": day_key, "hi": hi, "lo": lo,
                                             "spec": spec, "result": {"margin": False}}
                save_state(st)
                continue
            pend = mt5.orders_get(symbol=s["symbol"]) or []
            matches = [
                o for o in pend
                if abs(o.price_open - spec["buy_stop"]["price"]) < 0.5
                or abs(o.price_open - spec["sell_stop"]["price"]) < 0.5
            ]
            if matches:
                st["brackets"][s["name"]] = {"date": day_key, "recovered": True,
                                             "hi": hi, "lo": lo, "spec": spec}
                log(f"recovered [{s['name']}] bracket for {day_key}")
                save_state(st)
                continue
            res = place_bracket(st, spec, s["name"], s["symbol"], lot)
            st["brackets"][s["name"]] = {"date": day_key, "hi": hi, "lo": lo,
                                         "spec": spec, "placed_at": now(), "result": res}
            save_state(st)

    # housekeeping: expire stale brackets FIRST (every pass, not just at CANCEL_HOUR), then the
    # end-of-day backstop and the force-close.
    expire_stale_brackets(st)
    if hour >= CANCEL_HOUR:
        for s in sleeves:
            cancel_pending(st, s["symbol"])
    if hour >= CLOSE_HOUR:
        for s in sleeves:
            close_positions(st, s["symbol"])
    if tnow.dayofweek == 4 and hour >= CLOSE_HOUR:  # Friday: weekend close
        for s in sleeves:
            close_positions(st, s["symbol"])

    record_trades(st, sleeves)
    st = reconcile(st)
    save_state(st)
    log(f"state: armed={st['armed']} pos={len(st['position'] or [])} "
        f"pending={len(st['pending'] or [])} brackets={list(st['brackets'])} "
        f"sleeves={len(sleeves)}")
    mt5.shutdown()


if __name__ == "__main__":
    main()