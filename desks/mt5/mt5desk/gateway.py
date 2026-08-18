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
from datetime import UTC, datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from mt5desk import provenance as _prov  # noqa: E402
from mt5desk.independence import measure_from_ledger  # noqa: E402
from mt5desk.config import desk_root, gateway_paused, terminal_path  # noqa: E402

BASE = desk_root()
STATE = BASE / "data" / "gateway_state.json"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "gateway.log"

TERMINAL = terminal_path()
MAGIC = 341953

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
    MAX_DRAWDOWN_TOLERANCE,
    Q_OPT,
)
DIST_USD = 19.1         # ~1.2xATR stop distance (USD/oz), used for auto lot scaling
CONTRACT_OZ = 100
FX_EUR = 0.92
RR = 2.0
ATR_N = 20
CANCEL_HOUR = 20.5      # cancel unfilled brackets at 20:30 UTC
CLOSE_HOUR = 19.5       # force-close positions at 19:30 UTC
PROMOTED_MIN_EQUITY = 300.0  # EUR: below this, promoted sleeves stay dormant
                             # (0.01 lot at 300 EUR ~= 5.9% risk/trade ~= validated 5.5%)


def promoted_lot(equity: float, live_n: int, dist_usd: float | None = None) -> float:
    """Dynamic lot for promoted sleeves: auto_lot(equity, dist) x ramp.

    Ramp earns full authority only with forward proof: 0.25x before 50 live
    trades, 0.5x before 200, 1.0x after 200. Floor 0.01, cap 5.0.

    `dist_usd` is the sleeve's own stop and is passed through for the same reason
    `auto_lot` takes it: a promoted sleeve on a wide session runs the same 2.8x
    overshoot as an armed one, and the ramp would have made it look deliberate.
    """
    ramp = 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)
    lot = auto_lot(equity, dist_usd) * ramp
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


#: EUR put at risk by the venue's smallest tradeable position on gold. Below the equity where
#: this equals Q_OPT, the FLOOR sets the risk and the policy does not -- deliberately kept, so a
#: small account can trade and compound up rather than being locked out, but never silently.
MIN_LOT_RISK_EUR = 0.01 * DIST_USD * CONTRACT_OZ * FX_EUR   # ~17.57


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


def realised_q(equity: float, dist_usd: float | None = None) -> float:
    """The risk fraction the account WILL actually run, after the 0.01-lot floor.

    Not the same as Q_OPT whenever equity is small, and that gap is the whole point of this
    function existing. `auto_lot` used to clamp to 0.01 inside a `min(max(...))` and return only
    the lot, so a book configured for 0.75% could run at 5.9% with nothing in the code, the log
    or the state file ever saying so. A policy number that the venue silently overrides is not a
    policy.

    `dist_usd` IS THE SLEEVE'S OWN STOP where the caller knows it. See `auto_lot`.
    """
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    lot = max(_lot_steps(Q_OPT * equity / (d * CONTRACT_OZ * FX_EUR)), 0.01)
    return float(lot * d * CONTRACT_OZ * FX_EUR / equity) if equity > 0 else 0.0


def auto_lot(equity: float, dist_usd: float | None = None) -> float:
    """Fixed-fractional sizing: Q_OPT of equity per trade, floored at the venue minimum.

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
    lot = _lot_steps(Q_OPT * equity / (d * CONTRACT_OZ * FX_EUR))
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

#: Never exceed this however good the diversification looks. Correlations rise in exactly the
#: regime where the budget would be spent, and a measured k_eff is an estimate from calm. Raised
#: from 10% only because the budget is now solved against an explicit drawdown target -- the
#: ceiling is a backstop against a bad k_eff estimate, not the operative limit.
MAX_HEAT_CEILING = 0.15


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
    q_star = Q_OPT
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

    ORDER IS PRESERVED, so the caller's own priority decides who is dropped -- and the gold book
    is placed first by `sleeve_set()`, which makes the armed, human-authorised sleeves senior to
    anything the promoter added on its own. A cap that dropped sleeves arbitrarily could silently
    retire the one book with forward evidence behind it in favour of three that have none.
    """
    if equity <= 0 or not sleeves:
        return list(sleeves), None
    q = per_sleeve_q if per_sleeve_q is not None else realised_q(equity)
    if q <= 0:
        return list(sleeves), None
    budget = heat_budget(k_eff)
    room = int(budget / q)
    if room >= len(sleeves):
        return list(sleeves), None
    dropped = [s.get("name", "?") for s in sleeves[max(room, 0):]]
    note = (f"PORTFOLIO HEAT CAP: {len(sleeves)} sleeves x {q:.2%} = "
            f"{len(sleeves) * q:.1%} exceeds {budget:.1%} "
            f"(k_eff {'unmeasured' if k_eff is None else format(k_eff, '.2f')}); "
            f"admitting {max(room, 0)}, deferring {dropped}")
    return sleeves[:max(room, 0)], note


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


def margin_ok(symbol: str, lot: float, price: float) -> bool:
    """Skip a sleeve if margin would be tight (machine kill switch)."""
    acc = mt5.account_info()
    if acc is None or acc.margin_free <= 0:
        return False
    need = mt5.order_calc_margin(symbol, mt5.ORDER_TYPE_BUY, lot, price)
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
    for side in ("buy_stop", "sell_stop"):
        s = spec[side]
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY_STOP if side == "buy_stop" else mt5.ORDER_TYPE_SELL_STOP,
            "price": s["price"],
            "sl": s["sl"],
            "tp": s["tp"],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "deviation": 20,
            "magic": MAGIC,
            "comment": f"DW{sleeve}",
        }
        res = mt5.order_send(req)
        code = res.retcode if res else None
        if code == 10017:
            log("ORDER FAILED: trade disabled - enable 'Allow algorithmic trading' "
                "in terminal Options > Expert Advisors, and check account auth")
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
    return {"shadow": False, "orders": sent}


def cancel_pending(st: dict, symbol: str) -> None:
    if st["armed"]:
        for o in mt5.orders_get(symbol=symbol) or []:
            mt5.order_delete(o.ticket)
            log(f"cancelled pending ticket {o.ticket} ({symbol})")
    else:
        log("SHADOW would cancel unfilled brackets")


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


def record_trades(st: dict, sleeves: list[dict]) -> None:
    """Append closed trades (deal OUT with DW comment) to the live ledger.

    r_multiple: quote-currency P&L per lot / entry-risk distance per lot
    (entry risk = bracket SL distance x contract size in quote units).
    """
    if not st["armed"]:
        return
    try:
        day_start = datetime.combine(datetime.now(tz=UTC).date(),
                                     datetime.min.time(), tzinfo=UTC)
        deals = mt5.history_deals_get(day_start, datetime.now(tz=UTC), magic=MAGIC) or []
    except Exception:
        return
    written = 0
    for d in deals:
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        comment = (d.comment or "")
        if not comment.startswith("DW"):
            continue
        sleeve = comment[2:]
        sym_info = mt5.symbol_info(d.symbol)
        if sym_info is None:
            continue
        # risk per lot at entry: SL distance x contract (quote units)
        pl_quote = float(d.profit) + float(d.commission or 0.0) + float(d.swap or 0.0)
        risk_quote = (d.price_open - d.sl if d.type == mt5.POSITION_TYPE_BUY
                      else d.sl - d.price_open)
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
               "fill_price": float(d.price_open), "sl": float(d.sl), "tp": float(d.tp),
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


def sleeve_set() -> list[dict]:
    """All active sleeves: gold book + promoted, with window metadata."""
    sleeves = []
    for label, sig_hour, rng in GOLD_WINDOWS:
        sleeves.append({"name": f"gold_{label}", "symbol": "XAUUSD",
                        "window": label, "sig_hour": sig_hour, "rng": rng,
                        "lot": "auto", "status": "LIVE"})
    for s in load_sleeves():
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
    k_eff, k_why = measure_from_ledger(
        ledger_rows(), _prov.current_account(mt5.account_info()))
    log(k_why)
    sleeves, heat_note = cap_by_heat(sleeves, equity, k_eff=k_eff)
    if heat_note:
        log(heat_note)
    if st["last_bracket_date"] == day_key:
        for s in sleeves:
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
            lot = auto_lot(equity, dist) if s["lot"] == "auto" else (
                promoted_lot(equity, sleeve_live_n(s["name"]), dist) if s["lot"] == "auto_ramp"
                else float(s["lot"]))
            log(f"[{s['name']}] stop ${dist:.2f} -> lot {lot:.2f} "
                f"(realised q {realised_q(equity, dist):.2%})")
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

    # housekeeping: cancel unfilled brackets, force-close positions
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