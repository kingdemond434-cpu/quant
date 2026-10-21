"""E8 GOLD WINDOWS -- the desk's gold book, on the prop account.

PRINCIPAL 2026-09-16: "replace E8's book with the gold sleeves we use now". The evidence was
one-sided. Live on the MT5 account the gold windows were the only mechanism with a record
(gold_asia 9 trades +117 EUR, gold_london_am 7 trades +52, gold_afternoon 5 trades +10, 67%
wins, mean +0.36R) while E8 had lost most of its 911 USD on the `discovered` forex sleeves that
are now banned, and its remaining forex certificates had no live proof either way.

WHAT THIS IS. The MT5 gateway's bracket lane, on TradeLocker: at each window's signal hour the
day's range is read from the same XAUUSD H1 bars the gateway reads (the terminal on this box;
server clock, exactly as `decision_core.GOLD_WINDOWS` is written), `bracket_from_bars` builds
the same buy-stop/sell-stop pair with the same ATR-floored stop and the same RR target, and the
pair is sent as two resting stop orders with their stop and target attached. One fill cancels
the other leg (OCO); an unfilled pair is cancelled after BRACKET_TTL_HOURS; positions are closed
at CLOSE_HOUR and any resting leg cancelled at CANCEL_HOUR -- the gold book's own end of day.

WINDOWS RUN IN PARALLEL, AND ONLY THE OPPOSING LEG STANDS DOWN. While an XAU position is open,
the due window still places the leg that AGREES with it and skips only the one that would trade
against it (`book_direction` / `OPPOSING_LEG`); an unreadable position side defers the whole
bracket, as does an unreadable position book. The measurement behind that rule, and the cost of
deferring both legs instead, is recorded at the placement block in `run`.

SIZED FOR THIS ACCOUNT, NOT COPIED FROM THE OTHER. E8 risks RISK_FRAC of equity per trade
(`docs/PROP_FIRM_E8.md`: 0.50%) against the leg's own stop distance, through the E8 executor's
`lot_for_risk`, which reads the venue's own contract size.

SHADOW UNLESS data/E8_GOLD_ARMED EXISTS. Unarmed passes log the exact orders they would send.
The daily guard (`e8_guard.assess`, the one guard, shared with the E8 executor) stands new
placements down on any verdict but OK; management of what is already open never stands down.
ONE GOLD TRADE AT RISK AT A TIME: a window waits while an earlier XAU position still has its stop
short of break-even or an earlier bracket still rests (`one_at_risk_blocker`), and as a fail-safe
the gold risk committed plus its own must fit the guard's room to today's floor (SLIP_BUFFER).
A leg that would need more than GOLD_MAX_LOT is sent at the ceiling, smaller, never skipped.

    python prop/e8_gold.py            one pass, shadow unless armed
    python prop/e8_gold.py --armed    one pass, armed for this pass only
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import position_manager as _pm  # noqa: E402
from mt5desk.decision_core import (  # noqa: E402
    ATR_N,
    BRACKET_TTL_HOURS,
    CANCEL_HOUR,
    CLOSE_HOUR,
    GOLD_WINDOWS,
    OPPOSING_LEG,
    atr_last,
    book_direction,
    bracket_from_bars,
    h1_frame,
    window_end_hour,
    window_session_ended,
)
from mt5desk.kelly_sizing import (  # noqa: E402
    CERT_BOOK_FILE,
    load_cert_book,
    load_kelly_survival,
)

from prop import e8_evidence  # noqa: E402

SYMBOL = "XAUUSD"
#: Per-trade risk on the prop account, as a fraction of equity (docs/PROP_FIRM_E8.md).
RISK_FRAC = 0.005
#: The survival-constrained growth solve (research/kelly_survival.py; principal 2026-09-30:
#: "maximum aggressiveness within survival"). Its `e8` block names each window's risk fraction:
#: the fastest median pass whose P(floor) + P(daily breach) stays under EPS_STOP. Absent, stale
#: or not OK -> every window keeps RISK_FRAC, exactly as before the solve existed.
KELLY_FILE = DESK / "reports" / "KELLY_SURVIVAL.json"
STATE = DESK / "data" / "e8_gold_state.json"
OUT = DESK / "reports" / "E8_GOLD.json"
INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
ARMED_MARKER = DESK / "data" / "E8_GOLD_ARMED"
GUARD = DESK / "data" / "e8_guard_state.json"
LOG = DESK / "logs" / "e8_gold.log"
TAG = "E8gold"
#: XAUUSD's price grid, used only when the terminal cannot state `trade_tick_size`.
STOP_STEP = 0.01
# A LEG THE VENUE DROPPED IS RETRIED, NOT FORGOTTEN (2026-09-30). TradeLocker answered a send with
# an HTML page on 2026-09-17, 09-22 and 09-28; the pass recorded REJECTED, wrote the window as
# placed, and `plan` never looked at it again, so each of those days traded half a bracket. A
# failed leg now rides in its window's `failed` block and is re-sent on each 5-minute pass while
# its session is open, its twin has not filled and the level is still ahead of the price.
MAX_LEG_RETRIES = 12
# How close a resting venue order must sit to a failed leg's level to be that leg: the send that
# "failed" may have reached the venue before the reply broke, and sending again would double it.
LEG_MATCH_TOL = 0.05
#: How far BEFORE the failed send an order's own timestamp may sit and still be that send. The
#: venue stamps orders on the broker clock (UTC+2/+3), so a real UTC send time sits up to three
#: hours earlier than the stamp of the order it created; anything older is some other order.
LEG_MATCH_WINDOW_MS = 10 * 60 * 1000
XAU_OZ_PER_LOT = 100.0  # fallback for a leg journalled before risk_usd was kept on it
#: With no own order to measure the venue clock against, the send-time bound widens to this: a
#: box clock that runs fast must not hide a send that landed. The other fields (instrument, qty,
#: side, level, not a journal id) still have to agree, and a fill older than this still cannot.
UNMEASURED_SKEW_MS = 24 * 3600 * 1000
#: The growth-governance rail the unowned-position block is billed under (libs/portfolio/rails).
UNOWNED_BLOCK_RAIL = "e8_unowned_position_block"
# CONCURRENT OPEN RISK (2026-10-20). The three windows place independently and the AGREEING leg is
# placed while an earlier window is still open, so three windows at 0.75% each can be live in
# the same direction at once: 2.25% of the account to the stops, and more once a stop fills
# through its level. E8's daily floor is 2.5%. Before any window is placed, the risk already
# committed (open positions to their current stops, this lane's resting legs) plus the new
# window's must fit inside the guard's `room_to_daily_floor`, after both of these:
#: Stops on this venue fill at market, not at the level: 2026-09-24 a buy stop filled 24 points
#: through. Every committed dollar is grossed up by this before it is compared with the room, so
#: 2.25% of stop risk reads as ~2.8% and cannot be placed against a 2.5% floor.
SLIP_BUFFER = 1.25
#: Kept clear of the floor on top of the buffer: spread and commission on the closes, and the
#: equity read being seconds old. 0.10% of the starting balance.
ROOM_MARGIN_USD = 100.0
# A STOP MOVE THE VENUE KEEPS REFUSING IS BOUNDED (2026-10-20). On 2026-09-25 an asia short's
# break-even ratchet was refused by TradeLocker pass after pass; each refusal was logged and the
# same modify re-sent five minutes later, forever, while the trade gave back ~680 USD. After this
# many consecutive venue refusals for one position the lane stops re-sending: a position in profit
# beyond the break-even trigger is closed at market (the protection the stop could not give),
# otherwise its existing stop is held and the refusal raised as an alert.
MAX_STOP_REFUSALS = 3
# A LOT CEILING ON EVERY GOLD LEG (2026-10-20). `lot_for_risk` sizes a leg as the window's risk
# over its stop distance and nothing bounded the quotient: a tight range at 1% of a 100k account
# needs 0.75 lots at a 13.3-point stop and 2.0 at a 5-point one, and a stop that tight on gold is
# inside the noise a stop order fills through. What the ceiling really bounds is DOLLARS PER POINT
# of fill-through: at 0.75 lots a 2,500 USD daily floor takes a 23-27 point slip to reach.
#
# v2 (audit HOLD on 6f94d45cc, 2026-10-20): SHRINK, NEVER SKIP. v1 skipped the whole window, which
# fails growth-governance Rule 1: a tight stop is exactly where a capped leg is safe (its risk,
# ceiling x stop x contract, is at most the certified risk, and the dollars-per-point bound is
# kept), and skipping forwent 38-87 USD a window against <= 35 shrunk. So every leg over the
# ceiling is sent AT the ceiling; the window's budget is re-checked on the shrunk risk plus the
# points-slip allowance (`bracket_slip`, points), and v4 FITS the lot to that budget rather than
# deferring a window that can never pass it; and the risk withheld is journalled (status
# RAIL_SHRUNK, rail LOT_CEILING_RAIL, reason LOT_CEILING_REASON) and published two-sided by
# `research/missed_growth.published_e8_gold_lines` -- the risk withheld, the saving UNMEASURED.
GOLD_MAX_LOT = 0.75
#: E8's own position cap on XAUUSD, in lots. An override above it is no ceiling at all.
GOLD_MAX_LOT_CAP = 20.0
#: The box may move the ceiling without a code change: {"max_lot": <lots>}. Absent means
#: GOLD_MAX_LOT. Unreadable, non-numeric, non-finite, <= 0, above GOLD_MAX_LOT_CAP or below the
#: venue's minimum lot (which would idle the lane) also means GOLD_MAX_LOT, said in the pass
#: report -- a bad file never switches the ceiling off, and never sets one the venue cannot send.
GOLD_MAX_LOT_FILE = DESK / "data" / "E8_GOLD_MAX_LOT.json"
#: The name the withheld risk is journalled under (status RAIL_SHRUNK, missed_growth_risk_usd).
#: Not yet in libs/portfolio/rails.py, which is a sealed file: registering it is the principal's.
LOT_CEILING_RAIL = "e8_gold_lot_ceiling"
#: The decision reason code a shrunk window carries (prop/e8_evidence: R_LOT_CEILING, NOT exempt
#: in scripts/check_placement_interlock.py).
LOT_CEILING_REASON = "lot_ceiling"
# A STAND-DOWN CANCELS THIS LANE'S RESTING LEGS (2026-10-20). A guard verdict other than OK
# (STOOD_DOWN, CAPPED, BREACHED, PASSED) used to stop new placements only, so the twin of a
# bracket placed before the verdict still rested at the venue and could fill into a day the guard
# had closed. Every pass on which `assess().may_open` is False now cancels this lane's own
# journalled entry orders still resting (`stand_down_cancels`); filled positions and their stops
# are never touched, and a cancel the venue refuses is logged and tried again next pass.
STAND_DOWN_CANCEL = "stand_down_cancel"
# A TWO-LEGGED BRACKET IS BUDGETED AGAINST TODAY'S FLOOR (2026-10-20; v4 per the audit HOLD on
# 3ce5aaf85). One fill cancels the other, but the OCO is this lane's 5-minute pass, not the
# venue's: in a fast spike both legs can fill and stop out before the pass sees the first. So
# both legs' risk to their stops PLUS ONE LEG'S SLIP IN POINTS at the lot sent must fit the
# nearer of the guard's floors:
#
#     sum(leg_risk) + slip_points x lot x contract  <=  min(room_to_daily_floor, room_to_static)
#
# SLIP IS IN POINTS, NEVER R. The worst measured fill-through, 24.13 points on 2026-09-24, was
# 0.82R of a 29.55-point stop, but 1.86R of a 13-point one and 0.22R of a 110-point one: a slip in
# R mis-prices every stop but the one it was measured on. 0 of 41 E8 window-days filled both legs,
# so one leg carries the slip. A bracket that does not fit is SHRUNK, both legs alike, until it
# does (`floor_fit_lots`), journalled RAIL_SHRUNK; only a leg under the venue minimum skips the
# window (RAIL_BLOCKED, with its reason).
#
# v5 (audit HOLD on 4effc032d302): the room is ALSO net of what is already committed -- open
# positions to their current stops measured from the mark, so a break-even (ratcheted) winner's
# open profit, which the floor can still take back, is counted -- and of ROOM_MARGIN_USD:
#
#     sum(leg_risk) + slip_points x sum(lots) x contract
#                   <=  min(room_to_daily_floor, room_to_static) - committed - ROOM_MARGIN_USD
#
# and, UNTIL THE CROSS-ACCOUNT OCO LANDS, EVERY leg carries the slip (`BRACKET_SLIP_ALL_LEGS`):
# the audit found 78 of 133 v4 sends overran the room in the case where both legs fill and both
# slip, which the lane's own 5-minute OCO cannot rule out in a spike.
#: The worst measured single-leg fill-through on this venue, in price points (2026-09-24).
DEFAULT_SLIP_POINTS = 24.13
#: Both legs of a bracket are budgeted to fill AND slip (v5). Set False only once the venue-side
#: cross-account OCO (claude/cross-account-oco-v2) cancels the twin on the first fill, at which
#: point one leg's slip is the case again. Protects the daily and static floors only.
BRACKET_SLIP_ALL_LEGS = True
#: Stop exits the lane must have measured before their p95 replaces DEFAULT_SLIP_POINTS.
MIN_SLIP_EXITS = 20
#: The lane's measured slip, written by `prop/e8_gold_slip.py` from its own stop exits:
#: {"status": "MEASURED", "slip_points": <p95, points>, "n", "measured_at", "sources"}. Absent,
#: not MEASURED, n < MIN_SLIP_EXITS, unreadable, non-finite or negative -> DEFAULT_SLIP_POINTS.
BRACKET_SLIP_FILE = DESK / "data" / "E8_GOLD_SLIP.json"
#: Where the lane records each stop exit it can see in the venue's order history (one row per
#: filled protective stop of a position its own entry opened), for `e8_gold_slip` to measure.
STOP_EXITS = DESK / "data" / "e8_gold_stop_exits.jsonl"
# A TAKE-PROFIT THE DAILY CAP WOULD STRIP IS SHRUNK, NOT REFUSED (v4). E8 strips profit above the
# daily cap at rollover, so a target past the guard's `profit_cap_headroom` earns nothing beyond
# it while its stop still costs in full. Refusing the trade (v3) cost most fresh days above about
# 105.3k equity to save 10-108 USD of stripped excess; the lot is now cut so the target fits the
# headroom (`profit_fit_lots`), and only a lot under the venue minimum skips.
#: The rails these binds are journalled under (RAIL_SHRUNK / RAIL_BLOCKED, missed_growth_risk_usd).
#: Each is a NON-EXEMPT evidence reason (prop/e8_evidence + scripts/check_placement_interlock):
#: lot_ceiling, bracket_daily_floor, daily_profit_cap.
DAILY_FLOOR_RAIL = "e8_gold_bracket_daily_floor"
PROFIT_CAP_RAIL = "e8_gold_daily_profit_cap"
#: Their decision reason codes (prop/e8_evidence; see the README's merge note for the fence).
DAILY_FLOOR_REASON = "bracket_daily_floor"
PROFIT_CAP_REASON = "daily_profit_cap"
# Terminal reconnection (2026-09-30: ~70 min of "No IPC connection" in one day). Each attempt
# drops the dead IPC handle and re-attaches; the waits are seconds inside a 5-minute pass.
MT5_RETRY_WAITS_S = (0.0, 2.0, 5.0, 15.0, 30.0)


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ pure decisions

def cert_gold_windows(cert: dict[str, float] | None) -> dict[str, float]:
    """The certified book's gold keys (`gold_asia`) as this lane's window names (`asia`). Pure."""
    return {k.removeprefix("gold_"): v for k, v in (cert or {}).items() if k.startswith("gold_")}


def window_risk(name: str, kelly: dict[str, float] | None) -> tuple[float, str]:
    """(risk fraction of equity for window `name`, where it came from). Pure.

    The solve's number when it holds one for this window -- 0 means the window stands aside
    because every size it could send lowers the pass rate or breaks survival -- else RISK_FRAC.
    """
    if kelly is not None and name in kelly:
        return float(kelly[name]), "kelly_survival"
    return RISK_FRAC, "policy RISK_FRAC"


def gold_max_lot(path: Path | None = None, *, min_lot: float | None = None
                 ) -> tuple[float, str]:
    """(the lot ceiling for one gold leg, where it came from). Never raises.

    `path` (default GOLD_MAX_LOT_FILE) may hold {"max_lot": <lots>}. A missing file is the
    default; a file that cannot be read, or a value that is not a finite number above zero, is
    above GOLD_MAX_LOT_CAP, or is below `min_lot` (the venue's minimum, when it is known), is
    also the default, with the reason in the source string -- never a ceiling of zero or none.
    """
    p = GOLD_MAX_LOT_FILE if path is None else path
    try:
        if not p.exists():
            return GOLD_MAX_LOT, "default GOLD_MAX_LOT"
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
        raw = doc.get("max_lot") if isinstance(doc, dict) else None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) \
                or not math.isfinite(float(raw)) or not float(raw) > 0:
            return GOLD_MAX_LOT, (f"default GOLD_MAX_LOT ({p.name} max_lot={raw!r} is not a "
                                  f"positive number)")
        if float(raw) > GOLD_MAX_LOT_CAP:
            return GOLD_MAX_LOT, (f"default GOLD_MAX_LOT ({p.name} max_lot={raw!r} is above "
                                  f"E8's {GOLD_MAX_LOT_CAP:g}-lot XAUUSD cap: no ceiling at all)")
        if min_lot is not None and float(raw) < float(min_lot) - 1e-12:
            return GOLD_MAX_LOT, (f"default GOLD_MAX_LOT ({p.name} max_lot={raw!r} is below the "
                                  f"venue minimum {float(min_lot):g}: it would idle the lane)")
        return float(raw), p.name
    except Exception as exc:
        return GOLD_MAX_LOT, f"default GOLD_MAX_LOT ({p.name} unreadable: {type(exc).__name__})"


def cap_lot(lot: float, max_lot: float, quantise: Any = None) -> tuple[float, bool]:
    """(the lot to send, whether the ceiling shrank it). Pure.

    A lot at or under the ceiling is returned as it came. One over it is sent AT the ceiling
    (passed through `quantise`, the venue's lot step, when given) -- shrunk, never skipped.
    """
    if not float(lot) > float(max_lot) + 1e-9:
        return float(lot), False
    capped = float(max_lot) if quantise is None else float(quantise(float(max_lot)))
    return min(capped, float(max_lot)), True


def shrunk_budget_risk(lot: float, stop_dist: float, contract_size: float,
                       slip_points: float = DEFAULT_SLIP_POINTS) -> float:
    """A shrunk leg's risk for the budget: its stop at the level PLUS `slip_points` of
    fill-through, at the leg's own dollars per point. Pure."""
    per_point = float(lot) * float(contract_size)
    return per_point * (float(stop_dist) + float(slip_points))


def ceiling_budget_lot(committed: float, room: float, stop_dist: float, contract_size: float,
                       slip_points: float) -> float:
    """The largest lot whose `shrunk_budget_risk` still passes `risk_budget_allows`. Pure.

    (committed + L x contract x (stop + slip)) x SLIP_BUFFER <= room - ROOM_MARGIN_USD, solved for
    L. v3 deferred a ceiling-shrunk window that failed this check, and at a stop under about 13
    points on a 100 oz contract it fails on every pass: never sent, never journalled. v4 sends L.
    """
    unit = float(contract_size) * (float(stop_dist) + float(slip_points))
    if not unit > 0:
        return 0.0
    return max(0.0, ((float(room) - ROOM_MARGIN_USD) / SLIP_BUFFER - float(committed)) / unit)


def bracket_slip(path: Path | None = None, *, window: str | None = None) -> tuple[float, str]:
    """(one leg's fill-through allowance in price POINTS, where it came from). Never raises.

    The measured p95 from `path` (default BRACKET_SLIP_FILE) once it holds at least
    MIN_SLIP_EXITS stop exits and is above zero; otherwise DEFAULT_SLIP_POINTS, the worst
    single-leg slip measured, with the reason in the source string. With `window`, that window's
    own p95 is used when its block is MEASURED, above zero, on at least MIN_SLIP_EXITS of its
    exits; otherwise the pooled rule above.
    """
    p = BRACKET_SLIP_FILE if path is None else path
    default = "default DEFAULT_SLIP_POINTS (worst measured single-leg slip, 2026-09-24)"
    try:
        if not p.exists():
            return DEFAULT_SLIP_POINTS, f"{default}: no {p.name}"
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(doc, dict):
            return DEFAULT_SLIP_POINTS, f"{default}: {p.name} is not an object"
        wins = doc.get("windows")
        wdoc = wins.get(window) if window and isinstance(wins, dict) else None
        if isinstance(wdoc, dict) and str(wdoc.get("status") or "") == "MEASURED":
            wn, wraw = wdoc.get("n"), wdoc.get("slip_points")
            if isinstance(wn, int) and not isinstance(wn, bool) and wn >= MIN_SLIP_EXITS \
                    and isinstance(wraw, (int, float)) and not isinstance(wraw, bool) \
                    and math.isfinite(float(wraw)) and float(wraw) > 0:
                return float(wraw), f"{p.name} [{window}] (p95 of {wn} stop exits)"
        n = doc.get("n")
        if str(doc.get("status") or "") != "MEASURED":
            return DEFAULT_SLIP_POINTS, f"{default}: {p.name} is {doc.get('status')}, n={n}"
        if isinstance(n, bool) or not isinstance(n, int) or n < MIN_SLIP_EXITS:
            return DEFAULT_SLIP_POINTS, (f"{default}: {p.name} has n={n!r}, under "
                                         f"{MIN_SLIP_EXITS} stop exits")
        raw = doc.get("slip_points")
        # A MEASURED p95 OF ZERO IS NOT "NO SLIP" (v5): stop orders fill at market, and twenty
        # exits that happened to fill at the level say nothing about the next spike. Zero,
        # missing, non-finite or negative all read the 24.13-point floor; never zero slip.
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) \
                or not math.isfinite(float(raw)) or float(raw) <= 0:
            return DEFAULT_SLIP_POINTS, f"{default}: {p.name} slip_points={raw!r} is not > 0"
        return float(raw), f"{p.name} (p95 of {n} stop exits)"
    except Exception as exc:
        return DEFAULT_SLIP_POINTS, f"{default}: {p.name} unreadable ({type(exc).__name__})"


def bracket_floor_need(leg_risk: dict[str, float], lots: dict[str, float], slip_points: float,
                       contract_size: float, *, all_legs: bool | None = None) -> float:
    """Every leg's risk to its stop plus the slip, in USD. Pure.

    With `all_legs` (default BRACKET_SLIP_ALL_LEGS) every leg slips `slip_points` at its own lot:
    both legs fill and both slip. Otherwise one leg slips, at the largest lot sent (v4)."""
    if not lots:
        return 0.0
    every = BRACKET_SLIP_ALL_LEGS if all_legs is None else bool(all_legs)
    slip_lots = (sum(float(x) for x in lots.values()) if every
                 else max(float(x) for x in lots.values()))
    return (sum(float(v) for v in leg_risk.values())
            + float(slip_points) * slip_lots * float(contract_size))


def floor_room(guard_decision: Any) -> float:
    """The nearer of the guard's two floors: today's (daily) and the account's (static)."""
    return min(float(guard_decision.room_to_daily_floor),
               float(guard_decision.room_to_static_floor))


def fit_lots(lots: dict[str, float], caps: dict[str, float], *, min_lot: float | None,
             quantise: Any = None) -> tuple[dict[str, float] | None, dict[str, float], str | None]:
    """Cut each leg to its cap: (new lots, {side: lot before} for the legs cut, None), or
    (None, {}, why) when a cut leg would fall under the venue minimum. Never raises a lot. Pure.
    """
    out: dict[str, float] = {}
    before: dict[str, float] = {}
    for side, lot in lots.items():
        cap = float(caps.get(side, math.inf))
        if float(lot) <= cap + 1e-12:
            out[side] = float(lot)
            continue
        if not cap > 0 or (min_lot is not None and cap < float(min_lot) - 1e-12):
            return None, {}, (f"{side} would need {max(cap, 0.0):.4f} lots, under the venue "
                              f"minimum {float(min_lot or 0):g}")
        q = float(quantise(cap)) if quantise is not None else cap
        out[side] = min(q, cap, float(lot))
        before[side] = float(lot)
    return out, before, None


def floor_fit_lots(lots: dict[str, float], dists: dict[str, float], *, slip_points: float,
                   room: float, contract_size: float, min_lot: float | None,
                   quantise: Any = None, all_legs: bool | None = None
                   ) -> tuple[dict[str, float] | None, str | None]:
    """Shrink BOTH legs so the bracket fits the floor: (new lots, None), or (None, why). Pure.

    One common lot L for every leg, the largest with sum(L x stop_k x contract) + n x slip_points
    x L x contract <= room, where n is the number of legs that slip (all of them under
    `all_legs`, default BRACKET_SLIP_ALL_LEGS; else one). A leg is never made bigger; a leg under
    the venue minimum cannot be sent.
    """
    if not lots:
        return dict(lots), None
    every = BRACKET_SLIP_ALL_LEGS if all_legs is None else bool(all_legs)
    n_slip = len(lots) if every else 1
    unit = float(contract_size) * (sum(float(dists[k]) for k in lots)
                                   + n_slip * float(slip_points))
    cap = float(room) / unit if unit > 0 else 0.0
    out, _before, why = fit_lots(lots, dict.fromkeys(lots, cap), min_lot=min_lot,
                                 quantise=quantise)
    if out is None:
        return None, f"bracket cannot fit {float(room):,.0f} USD of floor room even shrunk: {why}"
    risk = {k: float(dists[k]) * v * float(contract_size) for k, v in out.items()}
    need = bracket_floor_need(risk, out, slip_points, contract_size, all_legs=every)
    if need > float(room) + 1e-9:
        return None, (f"bracket cannot fit the floor: the shrunk legs still need {need:,.0f} USD "
                      f"against {float(room):,.0f}")
    return out, None


def leg_target_profit(spec_leg: dict[str, Any], lot: float, contract_size: float) -> float:
    """Dollars a leg makes if its take-profit fills at the level. Pure."""
    return (abs(float(spec_leg["tp"]) - float(spec_leg["price"])) * float(lot)
            * float(contract_size))


def profit_fit_caps(spec: dict[str, Any], sides: Any, headroom: float,
                    contract_size: float) -> dict[str, float]:
    """Each leg's largest lot whose take-profit still fits the cap headroom. Pure."""
    caps: dict[str, float] = {}
    for side in sides:
        per_lot = leg_target_profit(spec[side], 1.0, contract_size)
        caps[side] = max(0.0, float(headroom)) / per_lot if per_lot > 0 else math.inf
    return caps


def stop_exits_from_history(hist_rows: list[dict[str, Any]], filled: dict[int, int],
                            own: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """The protective-stop fills of positions this lane's own entries opened, from the venue's
    order history: one row per exit with its side, stop level and fill price. Pure.

    A row qualifies when it is FILLED, carries a stopPrice and a fill price, belongs to a position
    one of our entry orders opened, and is not itself one of our entry orders -- so a take-profit
    (a limit, no stopPrice), an entry stop and anything on a position we did not open never count.
    """
    entry_of = {int(pid): int(oid) for oid, pid in filled.items() if int(oid) in own}
    owned = set(entry_of)
    entry_fill: dict[int, float] = {}
    for h in hist_rows:
        try:
            if h.get("id") is not None and int(h["id"]) in own:
                entry_fill[int(h["id"])] = float(h.get("avgPrice") or h.get("filledPrice") or 0.0)
        except (TypeError, ValueError):
            continue
    out: list[dict[str, Any]] = []
    for h in hist_rows:
        try:
            if str(h.get("status") or "").lower() != "filled" or h.get("id") is None:
                continue
            oid, pid = int(h["id"]), int(h.get("positionId") or 0)
            if oid in own or pid not in owned:
                continue
            stop = float(h.get("stopPrice") or 0.0)
            fill = float(h.get("avgPrice") or h.get("filledPrice") or 0.0)
            side = str(h.get("side") or "").lower()
        except (TypeError, ValueError):
            continue
        if stop > 0 and fill > 0 and side in ("buy", "sell") \
                and math.isfinite(stop) and math.isfinite(fill):
            row: dict[str, Any] = {"order_id": oid, "position_id": pid, "side": side,
                                   "stop": stop, "fill": fill, "venue_ms": _order_ms(h)}
            leg = own.get(entry_of[pid]) or {}
            if leg.get("window"):
                row["window"] = str(leg["window"])
            try:
                trigger = float(leg.get("price") or 0.0)
            except (TypeError, ValueError):
                trigger = 0.0
            entry = entry_fill.get(entry_of[pid], 0.0)
            entry_side = str(leg.get("side") or "").lower()
            entry_side = {"buy_stop": "buy", "sell_stop": "sell"}.get(entry_side, entry_side)
            if trigger > 0 and entry > 0 and entry_side in ("buy", "sell") \
                    and math.isfinite(trigger) and math.isfinite(entry):
                row.update(trigger=trigger, entry=entry, entry_side=entry_side)
            out.append(row)
    return out


def _record_stop_exits(rows: list[dict[str, Any]], *, now: datetime) -> int:
    """Append the stop exits not yet journalled. Never raises; `publish_slip` re-measures."""
    try:
        from prop import e8_gold_slip
        seen = {int(r["order_id"]) for r in e8_gold_slip.read_stop_exits(STOP_EXITS)
                if r.get("order_id") is not None}
        new = [r for r in rows if int(r["order_id"]) not in seen]
        # THE ACCOUNT STAMP (v5, must-fix 7): the pass's HMAC `account_key`
        # (e8_evidence.account_key -> libs.ops.provenance.account_key, create=False), so a stop
        # exit joins the OCO books and the evidence rows. No helper or no key -> no stamp: never
        # the raw login, never a plain sha256 of it.
        akey = e8_evidence.bound_account_key()
        stamp = {"account_key": akey} if akey else {}
        if new:
            STOP_EXITS.parent.mkdir(parents=True, exist_ok=True)
            with STOP_EXITS.open("a", encoding="utf-8") as fh:
                for r in new:
                    fh.write(json.dumps({"at": now.isoformat(timespec="seconds"), **r, **stamp})
                             + "\n")
        return len(new)
    except Exception as exc:
        log(f"stop-exit journal not updated ({type(exc).__name__}: {exc})")
        return 0


def publish_slip(*, now: datetime) -> dict[str, Any]:
    """Re-measure the slip from the lane's stop-exit journal, write E8_GOLD_SLIP.json and return
    the publication for E8_GOLD.json: overall and PER WINDOW, in points, with n, p95, max,
    measured_at and sources. Called on every pass AFTER placement, so it can never delay a send.

    NEVER RAISES. Any failure is logged and published as UNMEASURED with the error, and the guard
    keeps DEFAULT_SLIP_POINTS (`bracket_slip` reads only a MEASURED file with n >= 20).
    """
    try:
        from prop import e8_gold_slip
        d = e8_gold_slip.refresh(exits=STOP_EXITS, out=BRACKET_SLIP_FILE,
                                 measured_at=now.date().isoformat())
        keep = ("status", "n", "unit", "slip_points", "provisional_p95_points", "p50_points",
                "max_points", "measured_at", "sources", "min_n", "windows")
        pub = {k: d[k] for k in keep if k in d}
        pub["guard_slip_points"] = bracket_slip()[0]
        return pub
    except Exception as exc:
        log(f"slip not published ({type(exc).__name__}: {exc}); guard keeps "
            f"{DEFAULT_SLIP_POINTS:g} points")
        return {"status": "UNMEASURED", "n": 0, "unit": "points",
                "measured_at": now.date().isoformat(), "sources": [],
                "error": f"{type(exc).__name__}: {exc}"[:160],
                "guard_slip_points": DEFAULT_SLIP_POINTS}


def stand_down_cancels(open_ids: set[int], filled: dict[int, int],
                       own: dict[int, dict[str, Any]]) -> list[int]:
    """This lane's own entry orders still RESTING at the venue: what a stand-down cancels. Pure.

    Only ids the lane journalled as its own sends (`own_entry_orders`) qualify, so a position's
    protective stop or target, and anything a human placed, are never in the list; an id the venue
    reports as filled is a position now and is left alone too.
    """
    return sorted(int(oid) for oid in open_ids if int(oid) in own and int(oid) not in filled)


def plan(df: Any, hour: float, state: dict, *, tick_size: float = 0.01,
         stops_level: int = 0) -> list[dict]:
    """Windows due NOW: not yet placed today, at or past their signal hour, before the cancel
    hour, with a formed range. Each entry carries the bracket spec exactly as the gateway
    would send it. Pure: bars, clock and state in, decisions out."""
    out: list[dict] = []
    windows = state.get("windows") or {}
    for name, sig_hour, rng in GOLD_WINDOWS:
        if name in windows:
            continue
        if hour < float(sig_hour) or hour >= CANCEL_HOUR:
            continue
        if window_session_ended(name, hour):
            # A late pass (restart, IPC outage) must not send a bracket off a range its own
            # session already left: 2026-09-21 all three windows went out at 20:29 server in one
            # pass, and 2026-09-24 a 3h-late london_am sat on the afternoon's level and both
            # stopped in the same second (-950 USD). See decision_core.window_session_ended.
            continue
        built = bracket_from_bars(df, rng, sig_hour, tick_size, stops_level)
        if built is None:
            continue
        hi, lo, spec = built
        out.append({"window": name, "hi": hi, "lo": lo, "spec": spec, "sig_hour": sig_hour})
    return out


def leg_is_legal(side: str, price: float, bid: float, ask: float) -> tuple[bool, str]:
    """A buy stop must rest above the ask and a sell stop below the bid, or the venue would
    fill it at market on arrival -- a different trade from the certified breakout."""
    if side == "buy_stop" and price <= ask:
        return False, f"buy stop {price:.2f} is at or below the ask {ask:.2f}"
    if side == "sell_stop" and price >= bid:
        return False, f"sell stop {price:.2f} is at or above the bid {bid:.2f}"
    return True, ""


def retry_decisions(state: dict, hour: float, bid: float, ask: float, filled: dict[int, int],
                    blocked: str | None = None) -> list[dict]:
    """What to do with each leg the venue failed to take: {"act": "retry"|"abandon"|"hold"}.

    A leg is re-sent only while the certified trade still exists: its window's session is open
    (the same `window_session_ended` rule placement uses), the day is before the cancel hour, the
    other leg of the bracket has not filled (the OCO would cancel it at once), and the level is
    still AHEAD of the price -- a buy stop at or below the ask means the breakout already went
    without us, and sending it now would be a market fill, a different trade. A leg that would
    trade against an open position is held, never abandoned: the book may be flat next pass.
    Pure, so the rules are testable without a venue.
    """
    out: list[dict] = []
    for name, w in (state.get("windows") or {}).items():
        failed = w.get("failed") or {}
        if not failed or name.startswith("carried:"):
            continue
        twin_filled = w.get("position_id") is not None or any(
            leg.get("id") is not None and int(leg["id"]) in filled
            for leg in (w.get("orders") or {}).values())
        for side, leg in failed.items():
            base = {"window": name, "side": side, "leg": leg}
            if twin_filled:
                out.append({**base, "act": "abandon", "why": "the other leg filled"})
            elif hour >= CANCEL_HOUR or window_session_ended(name, hour):
                out.append({**base, "act": "abandon", "why": "the window's session is over"})
            elif int(leg.get("attempts") or 0) >= MAX_LEG_RETRIES:
                out.append({**base, "act": "abandon",
                            "why": f"{MAX_LEG_RETRIES} sends failed"})
            elif side == blocked:
                out.append({**base, "act": "hold",
                            "why": "would trade against an open XAU position"})
            else:
                legal, why = leg_is_legal(side, float(leg["price"]), float(bid), float(ask))
                out.append({**base, "act": "retry"} if legal else
                           {**base, "act": "abandon", "why": f"price already through: {why}"})
    return out


def _order_ms(o: dict) -> int | None:
    for k in ("createdDate", "created", "lastModified", "openDate", "time"):
        v = o.get(k)
        try:
            if v is not None and int(v) > 0:
                return int(v)
        except (TypeError, ValueError):
            continue
    return None


def _iso_ms(at: Any) -> int:
    """Milliseconds since the epoch of an ISO stamp; an unreadable stamp reads as NOW-FAR-FUTURE
    so nothing older can match it (fail closed: no adoption without a known send time)."""
    try:
        return int(datetime.fromisoformat(str(at)).timestamp() * 1000)
    except (TypeError, ValueError):
        return 2**62


def last_rollover_ms(at_ms: int) -> int:
    """The venue's last daily rollover (17:00 New York) at or before `at_ms`, in UTC ms. The
    widened send-time bound never reaches past it: yesterday's legs are not today's sends."""
    from zoneinfo import ZoneInfo
    ny = datetime.fromtimestamp(at_ms / 1000, tz=ZoneInfo("America/New_York"))
    roll = ny.replace(hour=17, minute=0, second=0, microsecond=0)
    if roll > ny:
        roll -= timedelta(days=1)
    return int(roll.timestamp() * 1000)


def venue_clock_skew_ms(journal: list[dict], rows: list[dict]) -> int | None:
    """How far the venue's order stamps run ahead of this box's clock, in ms, measured on the
    lane's OWN sends: each SENT journal row's box time against the venue's stamp on that order.
    The median, so one late-acknowledged send cannot move it. None when no own order is visible.

    WHY (audit 2026-09-30): the send-time bound compared the box clock with the venue's stamp,
    so a box running 15 minutes fast refused a send that had landed and sent it again. Measured
    this way the offset carries the box's skew AND whatever epoch the venue stamps in.
    """
    stamp = {int(o["id"]): ms for o in rows if o.get("id") is not None
             and (ms := _order_ms(o)) is not None}
    diffs = sorted(stamp[int(r["order_id"])] - _iso_ms(r.get("at")) for r in journal
                   if r.get("status") == "SENT" and r.get("order_id") is not None
                   and int(r["order_id"]) in stamp and _iso_ms(r.get("at")) < 2**62)
    return diffs[len(diffs) // 2] if diffs else None


def matching_resting_order(orders: list[dict], side: str, price: float, known_ids: set[int],
                           *, lot: float, instrument_id: int, since_ms: int) -> int | None:
    """The id of a venue order that IS this leg, if the failed send landed anyway.

    EVERY FIELD MUST AGREE, because a wrong match is worse than none (audit 2026-09-30: matching
    on side and level alone adopted a 40-hour-old 7-lot fill on ANOTHER instrument as this leg,
    and management then cancelled the live twin). So an order matches only when it is on this
    instrument, on this side, at this trigger level within LEG_MATCH_TOL, for this quantity, was
    created no earlier than LEG_MATCH_WINDOW_MS before the failed send, and is not an id the lane
    already owns -- today's legs AND every id in the intents journal, so yesterday's own leg
    cannot come back as today's after the rollover empties the windows. A row missing any of
    those fields does not match.
    """
    want = "buy" if side == "buy_stop" else "sell"
    for o in orders:
        oid = o.get("id")
        if oid is None or int(oid) in known_ids:
            continue
        if str(o.get("side") or "").lower() != want:
            continue
        try:
            if int(o.get("tradableInstrumentId") or 0) != int(instrument_id) or not instrument_id:
                continue
            qty = o.get("qty", o.get("quantity"))
            if qty is None or abs(float(qty) - float(lot)) > max(0.005, 0.01 * float(lot)):
                continue
            level = o.get("stopPrice") or o.get("price")
            if level is None or abs(float(level) - float(price)) > LEG_MATCH_TOL:
                continue
        except (TypeError, ValueError):
            continue
        made = _order_ms(o)
        if made is None or made < since_ms - LEG_MATCH_WINDOW_MS:
            continue
        return int(oid)
    return None


def position_since_failure(positions: list[dict], side: str, first_at: Any, state: dict,
                           filled: dict[int, int]) -> int | None:
    """The id of an open XAU position on this leg's side, opened at or after the failed send, that
    no window or carried row owns and no order of ours opened, or None. Such a position may be
    the "failed" send itself, filled; sending again would double it. Unknown open time counts."""
    want = "buy" if side == "buy_stop" else "sell"
    rows = [w for bucket in ("windows", "carried") for w in (state.get(bucket) or {}).values()]
    owned = {int(w["position_id"]) for w in rows if w.get("position_id") is not None}
    # Positions opened by orders this lane KNOWS it sent; any other fill may be the lost send.
    known = {int(leg["id"]) for w in rows for leg in (w.get("orders") or {}).values()
             if leg.get("id") is not None}
    ours = {int(pid) for oid, pid in filled.items() if int(oid) in known}
    try:
        since_ms = int(datetime.fromisoformat(str(first_at)).timestamp() * 1000)
    except (TypeError, ValueError):
        since_ms = 0
    for p in positions:
        if str(p.get("side") or "").lower() != want:
            continue
        pid = int(p.get("id") or 0)
        if pid in owned or pid in ours:
            continue
        opened = int(p.get("openDate") or 0)
        if opened == 0 or opened >= since_ms:
            return pid
    return None


def manage_actions(state: dict, hour: float, open_ids: set[int],
                   filled: dict[int, int], position_ids: set[int]) -> list[dict]:
    """What to do with today's windows, given the venue's resting order ids (`open_ids`), the
    map of filled order id -> position id (`filled`) and the XAUUSD position ids still open.

    Actions: {"act": "record_position"|"oco_cancel"|"ttl_cancel"|"close"|"eod_cancel", ...}.
    Pure, so the OCO and end-of-day rules are testable without a venue.
    """
    acts: list[dict] = []
    for name, w in (state.get("windows") or {}).items():
        legs = w.get("orders") or {}
        ids = {side: int(o["id"]) for side, o in legs.items() if o.get("id")}
        pos = w.get("position_id")
        if pos is None:
            for side, oid in ids.items():
                if oid in filled:
                    pos = int(filled[oid])
                    acts.append({"act": "record_position", "window": name, "side": side,
                                 "order_id": oid, "position_id": pos})
                    break
        if pos is not None:
            for side, oid in ids.items():
                if oid in open_ids and (oid not in filled):
                    acts.append({"act": "oco_cancel", "window": name, "side": side,
                                 "order_id": oid})
            if hour >= CLOSE_HOUR and int(pos) in position_ids:
                acts.append({"act": "close", "window": name, "position_id": int(pos)})
            continue
        resting = [oid for oid in ids.values() if oid in open_ids]
        if not resting:
            continue
        placed_hour = float(w.get("placed_hour") or 0.0)
        # THE BRACKET DIES WITH ITS SESSION, as the Fusion gateway's `bracket_deadline` has it.
        # A flat 6h TTL kept a london_am leg resting four hours into the afternoon, where it sat
        # beside the afternoon's own leg at almost the same level (2026-09-24: 4250.93 and
        # 4252.19, both filled at 15:01Z, both stopped). The flat TTL stays as the fallback for a
        # window the table does not know.
        end = window_end_hour(name)
        if hour >= CANCEL_HOUR:
            acts.extend({"act": "eod_cancel", "window": name, "order_id": oid} for oid in resting)
        elif (end is not None and hour >= end) or hour - placed_hour >= BRACKET_TTL_HOURS:
            acts.extend({"act": "ttl_cancel", "window": name, "order_id": oid} for oid in resting)
    return acts


def gold_positions(rows: list[dict], instrument_id: int) -> list[dict]:
    """The venue's open XAU positions, with no guess from comments or local state."""
    return [p for p in rows
            if int(p.get("tradableInstrumentId") or 0) == int(instrument_id)]


def _window_for_position(state: dict, position_id: int) -> tuple[str, dict] | None:
    for name, row in {**(state.get("carried") or {}), **(state.get("windows") or {})}.items():
        if row.get("position_id") is not None and int(row["position_id"]) == int(position_id):
            return str(name), row
    return None


def rollover_state(state: dict, today: str) -> dict:
    """The state a new server day starts from: no windows, every still-open position carried.

    THE ROLLOVER LOST POSITIONS (2026-09-29). It carried only yesterday's WINDOWS that had a
    recorded `position_id`, so (1) a position carried INTO yesterday was dropped at the next
    rollover, and (2) a leg that filled after the last pass of the day -- its `position_id` not
    yet recorded -- was dropped outright. Either way the ratchet, the break-even floor and the
    close hour stopped managing a live position. (1) is fixed here: every open carried row rides
    forward. (2) is fixed by `readopt_positions`, which re-derives ownership from the venue.
    """
    if state.get("date") == today:
        return state
    old_date = str(state.get("date") or "")
    carried = {n: w for n, w in (state.get("carried") or {}).items()
               if w.get("position_id") is not None and not w.get("closed")}
    for n, w in (state.get("windows") or {}).items():
        if n.startswith("carried:") or w.get("closed") or w.get("position_id") is None:
            continue
        carried[f"{old_date}/{n}" if n in carried else n] = w
    return {"date": today, "windows": {}, "carried": carried}


def own_entry_orders(journal: list[dict], state: dict) -> dict[int, dict]:
    """Every entry order THIS lane sent, by venue order id -> its leg (window, side, levels).

    TradeLocker has no magic number and this adapter sends no comment, so the desk's own mark
    on the venue is the order id it was handed at the send. Read from the intents journal (which
    survives the rollover and a lost state file) and from the state's own legs.
    """
    own: dict[int, dict] = {}
    for row in journal:
        if row.get("status") == "SENT" and row.get("order_id") is not None:
            own[int(row["order_id"])] = {k: row.get(k) for k in
                                         ("window", "side", "price", "sl", "tp", "lot")}
    for bucket in ("carried", "windows"):
        for name, w in (state.get(bucket) or {}).items():
            for side, leg in (w.get("orders") or {}).items():
                if leg.get("id") is not None:
                    own.setdefault(int(leg["id"]), {"window": name, "side": side,
                                                    **{k: leg.get(k) for k in
                                                       ("price", "sl", "tp", "lot")}})
    return own


def _today_leg_ids(state: dict) -> set[int]:
    return {int(leg["id"]) for n, w in (state.get("windows") or {}).items()
            if not n.startswith("carried:")
            for leg in (w.get("orders") or {}).values() if leg.get("id") is not None}


def readopt_positions(state: dict, filled: dict[int, int], position_ids: set[int],
                      own: dict[int, dict]) -> list[dict]:
    """Adopt into `state["carried"]` every open XAU position one of OUR entry orders opened
    that no window maps. Mutates `state`; returns one `readopt` action per adoption.

    Today's own legs are excluded: a fill this pass is recorded on its window by
    `manage_actions`, and adopting it twice would schedule two closes for one position.
    """
    today = _today_leg_ids(state)
    by_pos: dict[int, int] = {}
    for oid, pid in filled.items():
        if oid in own and oid not in today:
            by_pos.setdefault(int(pid), int(oid))
    acts: list[dict] = []
    for pid in sorted(position_ids):
        if _window_for_position(state, pid) is not None or pid not in by_pos:
            continue
        oid = by_pos[pid]
        leg = own[oid]
        key = f"readopted:{pid}"
        state.setdefault("carried", {})[key] = {
            "window": leg.get("window"), "readopted": True, "position_id": pid,
            "orders": {str(leg.get("side")): {"id": oid, **{k: leg.get(k) for k in
                                                            ("price", "sl", "tp", "lot")}}}}
        acts.append({"act": "readopt", "window": key, "position_id": pid, "order_id": oid})
    return acts


def stale_entry_orders(state: dict, open_ids: set[int], own: dict[int, dict]) -> list[int]:
    """Our own entry orders still resting at the venue that no window of TODAY owns.

    GTC LEGS OUTLIVED THE DAY (2026-09-29). Cancellation (OCO, TTL, end of day) walks today's
    windows only, and the rollover empties them -- so a GTC leg left resting across midnight was
    never cancelled again and could fill a day later, outside any window, unmanaged. Only ids
    this lane itself sent qualify: the venue's protective stop/target orders and anything a
    human placed are never touched.
    """
    today = _today_leg_ids(state)
    return sorted(oid for oid in open_ids if oid in own and oid not in today)


def trail_decision(position: dict, window: dict, bars: Any, current_stop: float,
                   *, cost_per_unit: float = 0.0, spread: float = 0.0
                   ) -> _pm.RatchetDecision | None:
    """The same H1 stop ratchet the Fusion gold gateway runs, pure for tests.

    TradeLocker and Fusion timestamps are both broker-clock epochs.  Filtering the already-read
    positional bar history against ``openDate`` therefore avoids the UTC/server offset bug that
    disabled Fusion management for whole trades.
    """
    import pandas as pd
    side = 1 if str(position.get("side") or "").lower() == "buy" else -1
    leg_name = "buy_stop" if side == 1 else "sell_stop"
    leg = (window.get("orders") or {}).get(leg_name) or {}
    entry = float(position.get("avgPrice") or leg.get("price") or 0.0)
    original_sl = float(leg.get("sl") or 0.0)
    dist = abs(entry - original_sl)
    opened_ms = int(position.get("openDate") or 0)
    if not (entry > 0 and current_stop > 0 and dist > 0 and opened_ms > 0):
        return None
    opened = pd.Timestamp(opened_ms, unit="ms", tz="UTC").floor("h")
    since = bars[bars.index >= opened]
    if len(since) < 2 or len(bars) < ATR_N + 1:
        return None
    atr = atr_last(bars)
    if not (atr > 0):
        return None
    extreme, stalled = _pm.extreme_and_stall(
        highs=[float(x) for x in since["high"]],
        lows=[float(x) for x in since["low"]], side=side)
    return _pm.ratchet(entry=entry, current_stop=float(current_stop), stop_distance=dist,
                       extreme=extreme, atr=atr, side=side, bars_since_extreme=stalled,
                       cost_per_unit=float(cost_per_unit), spread=max(0.0, float(spread)))


def stop_refusal_response(position: dict, window: dict, *, bid: float, ask: float,
                          cost_per_unit: float = 0.0) -> tuple[str, str]:
    """What to do with a position whose stop moves the venue has refused MAX_STOP_REFUSALS times.

    ("close", why) when it stands in profit at least BREAKEVEN_TRIGGER_R beyond its entry, net of
    the round-trip cost, at the price it would close on (bid for a long, ask for a short): the
    ratchet exists to protect exactly that profit and the venue will not let it. Otherwise
    ("hold", why): the stop already resting is kept and nothing more is sent. Pure.
    """
    side = 1 if str(position.get("side") or "").lower() == "buy" else -1
    leg = (window.get("orders") or {}).get("buy_stop" if side == 1 else "sell_stop") or {}
    entry = float(position.get("avgPrice") or leg.get("price") or 0.0)
    dist = abs(entry - float(leg.get("sl") or 0.0))
    if not (entry > 0 and dist > 0):
        return "hold", "entry or original stop unreadable; the resting stop is held"
    mark = float(bid) if side == 1 else float(ask)
    r_now = (side * (mark - entry) - float(cost_per_unit)) / dist
    trigger = _pm.BREAKEVEN_TRIGGER_R
    if r_now >= trigger:
        return "close", (f"+{r_now:.2f}R at {mark:.2f}, beyond the {trigger}R break-even trigger, "
                         f"and the venue refuses to move the stop: closed at market")
    return "hold", (f"{r_now:+.2f}R at {mark:.2f}, short of the {trigger}R trigger: the resting "
                    f"stop is held and no further stop move is sent")


def position_risk_usd(position: dict, stop: float, *, bid: float, ask: float,
                      contract_size: float) -> float:
    """Dollars this open position loses if its stop fills AT the level, measured from whichever
    is further from the stop: the entry, or the current mark (bid for a long, ask for a short).

    From the entry, a stop at or beyond it -- ratcheted to break-even or better -- risks nothing.
    From the mark, a winner still has its floating profit to give back, and the guard's room is
    measured on EQUITY, which already includes that profit; leaving it out would let a winning
    break-even leg fund new risk with money the floor can still take back.
    """
    side = str(position.get("side") or "").strip().lower()
    entry = float(position.get("avgPrice") or 0.0)
    qty = float(position.get("qty") or 0.0)
    if side not in ("buy", "sell") or not (entry > 0) or not (qty > 0) or not (stop > 0):
        raise ValueError(f"position {position.get('id')} has no readable side/entry/qty/stop")
    sign = 1.0 if side == "buy" else -1.0
    mark = float(bid) if side == "buy" else float(ask)
    per_unit = max(0.0, sign * (entry - stop), sign * (mark - stop))
    return per_unit * qty * float(contract_size)


def stop_is_at_risk(position: dict, stop: float) -> bool:
    """Is this position's stop still on the losing side of its entry (not yet at break-even)?"""
    side = str(position.get("side") or "").strip().lower()
    entry = float(position.get("avgPrice") or 0.0)
    return (entry - float(stop)) > 0 if side == "buy" else (float(stop) - entry) > 0


def one_at_risk_blocker(detail: dict[str, Any]) -> str | None:
    """ONE GOLD TRADE AT RISK AT A TIME ON E8 -- the reason a window must wait, or None.

    Gold is force-closed only at CLOSE_HOUR, so all three windows can be open together, and the
    agreeing-leg rule lets them stack in one direction. The max-growth simulation (2026-10-20,
    sizing/e8_three_gold_2026-10-20.md) put that at an 8-31% daily-breach rate at 0.75% per
    window, and at 0% breach with a 65-89% pass rate when a window waits while an earlier one is
    still at risk. "At risk" is a position whose stop is not yet at break-even or better, or a
    resting bracket of this lane that has not filled or been cancelled; a position ratcheted to
    break-even risks nothing and does not block.
    """
    risky = [str(r["position_id"]) for r in detail.get("positions") or [] if r.get("at_risk")]
    pending = sorted((detail.get("pending_brackets") or {}).keys())
    if risky:
        return (f"one gold trade at risk at a time: position(s) {', '.join(risky)} still have "
                f"their stop short of break-even")
    if pending:
        return (f"one gold trade at risk at a time: bracket(s) {', '.join(pending)} still rest "
                f"at the venue")
    return None


def committed_risk(positions: list[dict], open_orders: list[dict], journal: list[dict],
                   state: dict, *, bid: float, ask: float, contract_size: float
                   ) -> tuple[float, dict[str, Any]]:
    """Risk already on the account in gold, before a new window is placed.

    * every OPEN XAU position, to its current stop (`position_risk_usd`);
    * every RESTING entry leg this lane placed (its journalled `risk_usd`), with a bracket
      counted ONCE at its larger leg -- one fill cancels the other, so only one can become risk.

    Raises ValueError when a position's stop cannot be read: a position with no readable stop is
    unbounded risk, and new risk is not added on top of an unknown.
    """
    by_id = {int(o["id"]): o for o in open_orders if o.get("id") is not None}
    pos_rows: list[dict[str, Any]] = []
    for p in positions:
        stop_order = by_id.get(int(p.get("stopLossId") or 0)) or {}
        stop = float(stop_order.get("stopPrice") or p.get("stopLoss") or 0.0)
        usd = position_risk_usd(p, stop, bid=bid, ask=ask, contract_size=contract_size)
        pos_rows.append({"position_id": p.get("id"), "stop": stop, "risk_usd": round(usd, 2),
                         "at_risk": stop_is_at_risk(p, stop)})
    # THE JOURNAL IS THE LANE'S MARK ON THE VENUE; the state's legs cover a lost journal row.
    legs: dict[int, tuple[str, float]] = {}
    for row in journal:
        if row.get("status") != "SENT" or row.get("order_id") is None:
            continue
        risk = row.get("risk_usd")
        if risk is None:
            risk = (abs(float(row.get("price") or 0) - float(row.get("sl") or 0))
                    * float(row.get("lot") or 0) * float(contract_size))
        legs[int(row["order_id"])] = (f"{str(row.get('at') or '')[:10]}/{row.get('window')}",
                                      float(risk))
    today = str(state.get("date") or "")
    for bucket in ("carried", "windows"):
        for name, w in (state.get(bucket) or {}).items():
            for leg in (w.get("orders") or {}).values():
                if leg.get("id") is None or int(leg["id"]) in legs:
                    continue
                risk = (abs(float(leg.get("price") or 0) - float(leg.get("sl") or 0))
                        * float(leg.get("lot") or 0) * float(contract_size))
                legs[int(leg["id"])] = (f"{today}/{name}", risk)
    brackets: dict[str, float] = {}
    for oid, (group, risk) in legs.items():
        if oid in by_id:                                  # still resting at the venue
            brackets[group] = max(brackets.get(group, 0.0), risk)
    total = sum(r["risk_usd"] for r in pos_rows) + sum(brackets.values())
    return total, {"positions": pos_rows,
                   "pending_brackets": {k: round(v, 2) for k, v in brackets.items()}}


def risk_budget_allows(committed: float, new_risk: float, room: float) -> tuple[bool, str]:
    """May a window risking `new_risk` be added to `committed`, against `room` to today's floor?"""
    need = (float(committed) + float(new_risk)) * SLIP_BUFFER
    allowed = float(room) - ROOM_MARGIN_USD
    why = (f"committed {committed:,.0f} + this window {new_risk:,.0f} USD, x{SLIP_BUFFER} slippage "
           f"= {need:,.0f}, against {room:,.0f} to today's floor less a {ROOM_MARGIN_USD:,.0f} "
           f"margin = {allowed:,.0f}")
    return need <= allowed, why


# ------------------------------------------------------------------ the pass

class _CutBook:
    """One window's sizing as each rail cuts it: the lots, the legs' risk and the cuts made."""

    def __init__(self, sized: dict[str, tuple[float, str]], leg_risk: dict[str, float],
                 dists: dict[str, float], contract: float, risk_usd: float,
                 cuts: list[dict[str, Any]]) -> None:
        self.sized, self.leg_risk, self.dists = sized, leg_risk, dists
        self.contract, self.risk_usd, self.cuts = contract, risk_usd, cuts

    def apply(self, new: dict[str, float], before: dict[str, float], rail: str, reason: str,
              why: str, **extra: Any) -> None:
        """Take the cut legs to their new lots; record the cut with the risk it withheld."""
        risk_before = max(self.leg_risk.values()) if self.leg_risk else self.risk_usd
        for k, lot in new.items():
            if k in before:
                self.sized[k] = (lot, self.sized[k][1])
                self.leg_risk[k] = self.dists[k] * lot * self.contract
        if before:
            self.cuts.append({"rail": rail, "reason": reason, "why": why,
                              "unshrunk_lots": dict(before),
                              "withheld": max(0.0, risk_before - max(self.leg_risk.values())),
                              **extra})


def _cancel_on_stand_down(venue: Any, state: dict[str, Any], doc: dict[str, Any], *,
                          open_ids: set[int], filled: dict[int, int], armed: bool,
                          verdict: str) -> set[int]:
    """Cancel this lane's resting entry legs because the guard refuses new risk. Never raises.

    Returns the ids the venue acknowledged as cancelled. A refused or failed cancel is logged and
    left in place; the next pass, still refused by the guard, tries it again.
    """
    try:
        own = own_entry_orders(_journal_rows(), state)
        targets = stand_down_cancels(open_ids, filled, own)
    except Exception as exc:
        doc["stand_down_cancel_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
        log(f"stand-down cancel could not list our resting legs ({type(exc).__name__}: {exc}); "
            f"tried again next pass")
        return set()
    done: set[int] = set()
    for oid in targets:
        win = str(own[oid].get("window"))
        row = (state.get("windows") or {}).get(win) or (state.get("carried") or {}).get(win) or {}
        act: dict[str, Any] = {"act": STAND_DOWN_CANCEL, "window": win, "order_id": oid,
                               "verdict": verdict, "ok": False}
        try:
            if armed or not row.get("shadow", False):
                if venue.cancel(int(oid)):
                    act["ok"] = True
                    done.add(oid)
                    log(f"[{win}] {STAND_DOWN_CANCEL}: guard {verdict}; our resting entry order "
                        f"{oid} cancelled")
                else:
                    act["why"] = "venue did not acknowledge the cancel; tried again next pass"
            else:
                act.update({"ok": True, "shadow": True})
                log(f"[{win}] SHADOW would cancel resting entry order {oid} (guard {verdict})")
        except Exception as exc:
            act["why"] = f"{type(exc).__name__}: {exc}"[:160] + "; tried again next pass"
        if not act["ok"]:
            log(f"[{win}] {STAND_DOWN_CANCEL} FAILED for order {oid}: {act['why']}")
        doc["actions"].append(act)
    return done


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _journal_rows(limit: int = 5000) -> list[dict]:
    """The last `limit` rows of the intents journal; unreadable -> none (no adoption, no cancel)."""
    return _journal_read(limit) or []


def _journal_read(limit: int = 5000) -> list[dict] | None:
    """The journal's rows, or None when it is missing or unreadable (non-UTF-8 included).

    None is not "no rows": the retry path needs the journal's order ids to refuse yesterday's own
    legs, so it treats None as blind and skips the pass (audit 2026-09-30).
    """
    try:
        lines = INTENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    except (OSError, UnicodeDecodeError):
        return None
    rows: list[dict] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _record(row: dict[str, Any]) -> bool:
    """Append one intent row. Returns False -- LOUDLY -- when the write failed.

    THIS WAS `except OSError: pass`, AND THIS JOURNAL IS NOT TELEMETRY. TradeLocker carries no
    magic number and no comment, so `own_entry_orders` recognises the desk's own resting orders
    on the venue ONLY by the order id written here at the send. A lost row is an order the next
    pass cannot re-adopt or stale-cancel: a GTC leg left resting with nothing managing it. The
    failure is logged with the order id, so the one place it survives is readable, and the
    caller records it on the pass report."""
    try:
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        return True
    except OSError as exc:
        log(f"INTENT JOURNAL WRITE FAILED ({type(exc).__name__}: {exc}) for "
            f"{row.get('window')} {row.get('side')} order {row.get('order_id')} "
            f"status {row.get('status')}: this order is recorded in this log line only")
        return False


def run(venue: Any, mt5: Any, *, armed: bool = False) -> dict[str, Any]:
    """One pass. `venue` is a connected TradeLockerVenue; `mt5` the MetaTrader5 module (bars
    and the server clock, read exactly as the gateway reads them)."""
    from mt5desk import order_door
    from prop.e8_executor import E8_ROUND_TRIP_PER_PRICE_UNIT, _quantise, lot_for_risk

    # ONE DOOR FOR MONEY: place_stop / modify_stop / cancel / close go through the order door's
    # ledger, and a raise or an unacknowledged write is logged, never silent.
    venue = order_door.guard_venue(venue, caller="e8_gold", log=log)
    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "armed": bool(armed),
                           "symbol": SYMBOL, "placed": [], "actions": [], "skipped": []}
    # WHICH HOST RAN THIS PASS, AND ON WHICH ACCOUNT (prop/e8_evidence.py). Both reads never
    # raise; they are recorded on the report, the heartbeat and every decision row.
    host = e8_evidence.host_block()
    account = e8_evidence.account_label(venue)
    # Text clipped below is scrubbed of this account's id BEFORE it is cut (e8_evidence.clip).
    e8_evidence.bind_account(account)
    e8_evidence.bind_account_key(e8_evidence.account_key(venue))
    doc.update({"host": host, "account": account})
    tick = mt5.symbol_info_tick(SYMBOL)
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 400)
    if tick is None or rates is None or len(rates) < 60:
        doc["status"] = "NO_BARS"
        log("no XAUUSD tick or bars from the terminal; nothing decided")
        doc["heartbeat"] = e8_evidence.write_heartbeat(
            "NO_BARS", at=now, armed=armed, account=account, host=host, log=log)
        return doc
    import pandas as pd
    df = h1_frame(rates)
    tnow = pd.Timestamp(int(tick.time), unit="s", tz="UTC")
    hour = float(tnow.hour + tnow.minute / 60.0)
    today = str(tnow.date())
    doc.update({"server_time": tnow.isoformat(), "hour": round(hour, 3)})

    prior = _read_json(STATE, {})
    state = rollover_state(prior, today)
    # Evidence rows a failed write kept ride across the rollover (prop/e8_evidence.py); nothing
    # a placement reads is touched.
    e8_evidence.carry_pending(prior, state)
    acct = venue.account()
    equity = float(acct.get("equity") or acct.get("balance") or 0.0)
    risk_usd = equity * RISK_FRAC
    kelly = load_kelly_survival(KELLY_FILE, "e8")
    # THE PRINCIPAL'S CERTIFIED BOOK OVERRIDES THE SOLVE PER WINDOW (data/CERT_BOOK_LIVE.json,
    # 2026-10-07). Its gold keys are the gateway's (`gold_asia`); this lane names windows bare.
    cert = cert_gold_windows(load_cert_book(CERT_BOOK_FILE, "e8"))
    if cert:
        kelly = {**(kelly or {}), **cert}
    doc.update({"equity": equity, "risk_usd": round(risk_usd, 2),
                "cert_book_windows": cert or None,
                "sizing_source": "kelly_survival" if kelly is not None else "policy RISK_FRAC",
                "kelly_risk": kelly})
    # THE ONE GUARD DECIDES (2026-10-20). This read the raw `stood_down` flag out of the guard's
    # state file, which only the executor's `assess` call ever rolled to a new server day: on
    # 2026-10-15 a flag latched on 10-14 stood the gold book down from 00:01Z to 23:56Z with no
    # placement, and the flag-only read never saw CAPPED, BREACHED or PASSED at all. `assess` is
    # the verdict; it re-anchors a stale day itself. An equity that cannot be read is not
    # anchored on (a zero would be persisted as the day's start), and a guard that raises refuses.
    from prop import e8_guard
    guard_decision: Any = None
    if not equity > 0:
        stood_down = True
        doc["guard"] = "equity unreadable: no new placements this pass"
        log("guard not consulted: the venue reported no equity; managing open exposure only")
    else:
        try:
            guard_decision = e8_guard.assess(equity, now=now, state_path=GUARD)
            doc["guard_decision"] = guard_decision.as_dict()
            stood_down = not guard_decision.may_open
            if stood_down:
                doc["guard"] = (f"{guard_decision.verdict.value}: no new placements this pass "
                                f"({guard_decision.why})")
                log(f"guard {guard_decision.verdict.value}: {guard_decision.why}; managing open "
                    f"exposure only")
        except Exception as exc:
            stood_down = True
            doc["guard"] = e8_evidence.clip(
                f"guard unreadable ({type(exc).__name__}: {exc}", 200) + ")"
            log(f"guard raised {type(exc).__name__}: {exc}; no new placements this pass")

    bid, ask = venue.quote(SYMBOL)
    try:
        iid = venue.instrument_id(SYMBOL)
        venue_positions = venue.positions()
        xau_positions = gold_positions(venue_positions, iid)
    except Exception as exc:
        # An unreadable position book must fail CLOSED for new placements.  Otherwise the one
        # check intended to prevent a second/opposite XAU leg disappears precisely when the API
        # is unhealthy.
        iid, venue_positions, xau_positions = 0, [], []
        stood_down = True
        doc["positions_unreadable"] = e8_evidence.clip(f"{type(exc).__name__}: {exc}", 160)
        log("position book unreadable; no new E8 gold placement this pass")
    # -------------------------------------------------------------- placements
    # EVERY DUE WINDOW'S DECISION IS EVIDENCE (prop/e8_evidence.py): collected here, written once
    # after the placement block, only when a window's outcome or reason changes for the day.
    decided = e8_evidence.Decisions(
        risk_of=lambda n: equity * window_risk(n, kelly)[0] if equity > 0 else None)
    due_now = [] if stood_down else plan(df, hour, state)
    if stood_down:
        # Evidence only: the windows that WOULD be due, so a stand-down that lasts all day leaves
        # a row the placement interlock can read. Nothing below reads this list.
        try:
            code = e8_evidence.stand_down_reason(equity, guard_decision, doc)
            why = str(doc.get("guard") or doc.get("positions_unreadable") or code)
            for due in plan(df, hour, state):
                decided.note(due["window"], e8_evidence.DEFERRED, code, why)
        except Exception as exc:
            log(f"stand-down evidence not derived ({type(exc).__name__}: {exc})")
    # THE SELF-HEDGE RULE IS PER LEG, NOT PER BRACKET (principal, 2026-09-24).
    #
    # TradeLocker can hold opposite XAU positions, so a second two-sided bracket placed while one
    # window is live can fill AGAINST it: two spreads and two margin legs for a book whose net
    # exposure is smaller or zero.  That cost is real and the opposing leg still carries it.  What
    # was wrong was throwing away the harmless half with it -- the same-direction leg only adds to
    # a position the desk already wants, and deferring the whole bracket SERIALISES three windows
    # that are only +0.180 correlated, which is most of a month of pass time on a prop clock.
    #
    # MEASURED on this account's own record before the change, off the box's XAUUSD bars, over
    # 2026-09-17..24 (six trading days, the three windows, the live ratchet, E8's spread):
    #   * 4 recorded deferrals (09-22 afternoon, 09-23 london_am, 09-23 afternoon, 09-24
    #     london_am).  3 of the 4 would have filled; ALL THREE were SAME-DIRECTION, none opposing.
    #     +257.13 USD against the -16.20 the deferred-and-replaced versions actually made.
    #   * over the three days the deferral actually bound, +703 -> +976 USD, which is 43 -> 31 days
    #     to the 10,000 target -- the principal's modelled 45 -> 34, reproduced.
    #   * the only OPPOSING fill anywhere in the sample (09-21 london_am buy into an open short)
    #     lost the full -1.000R, -480.74 USD: the single worst trade of the run, and the whole
    #     difference between skipping the opposing leg and removing the check outright.
    # So the opposing leg is skipped and the agreeing leg is placed.  Per-trade risk is unchanged.
    direction = book_direction(xau_positions)
    blocked = OPPOSING_LEG.get(direction) if direction is not None else None
    if direction is None and due_now:
        # A side this code could not read is NOT a flat book.  Defer wholesale, and do not mark
        # the window placed: if the earlier trade exits while this window remains valid, the next
        # pass may still act.
        for due in due_now:
            why = (f"open XAU position(s) with an unreadable side: "
                   f"{', '.join(str(p.get('id')) for p in xau_positions)}; deferred to prevent "
                   f"self-hedging")
            doc["skipped"].append({"window": due["window"], "why": why})
            with contextlib.suppress(Exception):
                decided.note(due["window"], e8_evidence.DEFERRED,
                             e8_evidence.R_SIDE_UNREADABLE, why)
            log(f"[{due['window']}] DEFERRED: {why}")
        due_now = []
    committed: float | None = None
    contract = XAU_OZ_PER_LOT
    if due_now:
        # CONCURRENT OPEN RISK, measured once, before any window is placed (see SLIP_BUFFER).
        # Anything unreadable -- the order book, the journal, a position's stop -- refuses every
        # window this pass and marks none placed, so the next pass decides again.
        try:
            budget_orders = venue.orders(SYMBOL)
            journal = [] if not INTENTS.exists() else _journal_read()
            if journal is None:
                raise ValueError("the intents journal is unreadable, so this lane's resting "
                                 "legs cannot be counted")
            try:
                contract = float(venue.details(SYMBOL).get("contractSize") or XAU_OZ_PER_LOT)
            except Exception:
                contract = XAU_OZ_PER_LOT
            committed, doc["committed_risk"] = committed_risk(
                xau_positions, budget_orders, journal, state, bid=float(bid), ask=float(ask),
                contract_size=contract)
            doc["committed_risk"]["total_usd"] = round(committed, 2)
        except Exception as exc:
            why = (e8_evidence.clip(
                f"concurrent open risk unmeasurable ({type(exc).__name__}: {exc}", 200)
                   + "); no window placed this pass")
            for due in due_now:
                doc["skipped"].append({"window": due["window"], "why": why})
                with contextlib.suppress(Exception):
                    decided.note(due["window"], e8_evidence.DEFERRED,
                                 e8_evidence.R_RISK_UNMEASURABLE, why)
                log(f"[{due['window']}] DEFERRED: {why}")
            due_now = []
    room = float(guard_decision.room_to_daily_floor) if guard_decision is not None else 0.0
    try:
        _min = float(venue.min_lot(SYMBOL))
        venue_min_lot: float | None = _min if math.isfinite(_min) and _min > 0 else None
    except Exception:
        venue_min_lot = None
    max_lot, max_lot_src = gold_max_lot(min_lot=venue_min_lot)
    doc["lot_ceiling"] = {"max_lot": max_lot, "source": max_lot_src}
    slip_pts, slip_src = bracket_slip()
    doc["bracket_slip"] = {"slip_points": slip_pts, "source": slip_src, "windows": {}}
    placed_this_pass: list[str] = []
    for due in due_now:
        name, spec = due["window"], due["spec"]
        slip_pts, slip_src = bracket_slip(window=name)
        doc["bracket_slip"]["windows"][name] = {"slip_points": slip_pts, "source": slip_src}
        frac, frac_src = window_risk(name, kelly)
        if not frac > 0:
            doc["skipped"].append({"window": name, "why": (
                "stands aside: the survival-constrained growth solve "
                "(reports/KELLY_SURVIVAL.json) funds this window at 0 risk")})
            with contextlib.suppress(Exception):
                decided.note(name, e8_evidence.SKIPPED, e8_evidence.R_KELLY_ZERO,
                             doc["skipped"][-1]["why"], risk_usd=0.0)
            continue
        risk_usd = equity * frac
        # FIRST: one gold trade at risk at a time (`one_at_risk_blocker`). SECOND, a fail-safe
        # under it: everything committed plus this window, grossed up for slippage, must fit the
        # guard's room to today's floor. Either refusal defers the window without marking it
        # placed, so a later pass inside its session places it once the earlier risk is gone.
        blocker = one_at_risk_blocker(doc.get("committed_risk") or {})
        if blocker is None and placed_this_pass:
            blocker = (f"one gold trade at risk at a time: {', '.join(placed_this_pass)} was "
                       f"placed earlier in this pass")
        # The concurrent-risk budget is NOT checked here (audit HOLD on v4, must-fix 2): the lot
        # ceiling below FITS a capped leg to that budget first, and only an unshrunk window that
        # fails it is deferred under the exempt R_RISK_BUDGET, inside the sizing block.
        blocker_code = e8_evidence.R_ONE_AT_RISK
        if blocker is not None:
            doc["skipped"].append({"window": name, "why": blocker})
            with contextlib.suppress(Exception):
                decided.note(name, e8_evidence.DEFERRED, blocker_code, blocker, risk_usd=risk_usd)
            log(f"[{name}] DEFERRED: {blocker}")
            continue
        # SIZING, v4 (audit HOLD on 3ce5aaf85): every leg this window would send is sized BEFORE
        # any is sent, then each rail that binds CUTS the lot rather than refusing the window --
        #   1. the lot ceiling (GOLD_MAX_LOT), and the budget on the capped leg plus slip;
        #   2. today's floor (and the static one) for both legs plus one leg's slip in points;
        #   3. the daily profit cap: no target past the guard's headroom.
        # A cut is journalled RAIL_SHRUNK with the risk it withheld. A rail is a skip only when its
        # lot would fall under the venue minimum, and then it writes a RAIL_BLOCKED row with its
        # reason and marks the window spent. `sized[side]` is the lot the send loop sends.
        sized: dict[str, tuple[float, str]] = {}
        leg_risk: dict[str, float] = {}
        dists: dict[str, float] = {}
        for side in ("buy_stop", "sell_stop"):
            s = spec[side]
            if side == blocked or not leg_is_legal(side, float(s["price"]), float(bid),
                                                   float(ask))[0]:
                continue
            dist = abs(float(s["price"]) - float(s["sl"]))
            lot, basis = lot_for_risk(venue, SYMBOL, dist, risk_usd)
            sized[side] = (_quantise(lot, venue, SYMBOL), basis)
            # A LEG LIFTED TO THE VENUE MINIMUM RISKS MORE THAN ITS CERTIFIED RISK (v5, audit
            # should-fix): at a 0.1 minimum and a 100-point stop it is 1,000 USD, not the window's
            # 600. Its leg_risk is what it risks AT THE LOT IT WOULD SEND, so step 2 judges the
            # lifted lot; one that does not fit cannot be shrunk under the minimum and the window
            # is RAIL_BLOCKED with its reason -- a lot is never lifted above what fits.
            leg_risk[side] = max(risk_usd, dist * float(sized[side][0]) * float(contract))
            dists[side] = dist
        cuts: list[dict[str, Any]] = []
        rail_skip: dict[str, Any] | None = None

        def _quant(x: float) -> float:
            return float(_quantise(x, venue, SYMBOL))

        book = _CutBook(sized, leg_risk, dists, contract, risk_usd, cuts)
        _apply = book.apply
        try:
            # 1. THE LOT CEILING, then the budget on what the capped leg risks with its slip.
            capped, before, _ = fit_lots({k: v[0] for k, v in sized.items()},
                                         dict.fromkeys(sized, max_lot), min_lot=None,
                                         quantise=_quant)
            if capped is not None and before:
                over = ", ".join(f"{k} {v:g}" for k, v in sorted(before.items()))
                _apply(capped, before, LOT_CEILING_RAIL, LOT_CEILING_REASON,
                       f"lot ceiling: {over} lots shrunk to the {max_lot:g}-lot ceiling for one "
                       f"gold leg", max_lot=max_lot, max_lot_source=max_lot_src)
                caps = {k: ceiling_budget_lot(committed or 0.0, room, dists[k], contract,
                                              slip_pts) for k in before}
                fitted, cut, cut_why = fit_lots({k: sized[k][0] for k in sized}, caps,
                                                min_lot=venue_min_lot, quantise=_quant)
                if fitted is None:
                    rail_skip = {"rail": LOT_CEILING_RAIL, "reason": LOT_CEILING_REASON,
                                 "why": (f"lot ceiling: the capped leg cannot fit the "
                                         f"concurrent-risk budget with {slip_pts:g} points of "
                                         f"slip: {cut_why}"),
                                 "slip_points": slip_pts}
                elif cut:
                    _apply(fitted, cut, LOT_CEILING_RAIL, LOT_CEILING_REASON,
                           f"lot ceiling: capped leg cut further to fit the concurrent-risk "
                           f"budget with {slip_pts:g} points of slip",
                           slip_points=slip_pts, slip_source=slip_src)
            else:
                # Only an UNSHRUNK window reaches the exempt R_RISK_BUDGET deferral: the ceiling
                # fit above runs first and never defers (audit HOLD on v4, must-fix 2).
                unshrunk_risk = max(leg_risk.values()) if leg_risk else risk_usd
                fits, budget_why = risk_budget_allows(committed or 0.0, unshrunk_risk, room)
                if not fits:
                    blocker = f"concurrent risk would reach today's floor: {budget_why}"
                    doc["skipped"].append({"window": name, "why": blocker})
                    with contextlib.suppress(Exception):
                        decided.note(name, e8_evidence.DEFERRED, e8_evidence.R_RISK_BUDGET,
                                     blocker, risk_usd=unshrunk_risk)
                    log(f"[{name}] DEFERRED: {blocker}")
                    continue
            # 2. TODAY'S FLOOR (and the static floor) for both legs plus their slip, NET of what
            # is already committed and of ROOM_MARGIN_USD (v5, audit HOLD on v4, must-fixes 1
            # and 3): an open position's risk to its stop counts from the mark, so a break-even
            # winner's open profit -- which today's floor can still take back -- is not room.
            if rail_skip is None and sized:
                if guard_decision is None:
                    raise ValueError("no guard decision to budget against")
                room_floor = (floor_room(guard_decision) - float(committed or 0.0)
                              - ROOM_MARGIN_USD)
                lots_now = {k: v[0] for k, v in sized.items()}
                need = bracket_floor_need(leg_risk, lots_now, slip_pts, contract)
                if need > room_floor + 1e-9:
                    fit, fit_why = floor_fit_lots(lots_now, dists, slip_points=slip_pts,
                                                  room=room_floor, contract_size=contract,
                                                  min_lot=venue_min_lot, quantise=_quant)
                    floor_extra = {"slip_points": slip_pts, "slip_source": slip_src,
                                   "slip_all_legs": BRACKET_SLIP_ALL_LEGS,
                                   "room_to_floor": round(room_floor, 2),
                                   "committed_usd": round(float(committed or 0.0), 2),
                                   "room_margin_usd": ROOM_MARGIN_USD,
                                   "need_usd": round(need, 2)}
                    if fit is None:
                        rail_skip = {"rail": DAILY_FLOOR_RAIL, "reason": DAILY_FLOOR_REASON,
                                     "why": str(fit_why), **floor_extra}
                    else:
                        # Judged on what each leg actually risks at its lot from here on.
                        for k in fit:
                            leg_risk[k] = dists[k] * sized[k][0] * contract
                        slipping = "every leg's" if BRACKET_SLIP_ALL_LEGS else "one leg's"
                        _apply(fit, {k: lots_now[k] for k in fit if fit[k] < lots_now[k] - 1e-12},
                               DAILY_FLOOR_RAIL, DAILY_FLOOR_REASON,
                               (f"bracket floor: {len(fit)} legs plus {slip_pts:g} points of "
                                f"{slipping} slip needed {need:,.0f} USD against "
                                f"{room_floor:,.0f} to the nearer floor net of committed risk "
                                f"and margin; shrunk to fit"),
                               **floor_extra)
            # 3. THE DAILY PROFIT CAP: no target past the headroom the guard reports.
            if rail_skip is None and sized:
                headroom = float(guard_decision.profit_cap_headroom)
                caps = profit_fit_caps(spec, sized.keys(), headroom, contract)
                fitted, cut, cut_why = fit_lots({k: v[0] for k, v in sized.items()}, caps,
                                                min_lot=venue_min_lot, quantise=_quant)
                cap_extra = {"profit_cap_headroom_usd": round(headroom, 2)}
                if fitted is None:
                    rail_skip = {"rail": PROFIT_CAP_RAIL, "reason": PROFIT_CAP_REASON,
                                 "why": (f"daily profit cap: {headroom:,.0f} USD of counted "
                                         f"profit left today: {cut_why}"), **cap_extra}
                elif cut:
                    _apply(fitted, cut, PROFIT_CAP_RAIL, PROFIT_CAP_REASON,
                           (f"daily profit cap: target cut to fit the {headroom:,.0f} USD of "
                            f"counted profit left today; the excess would be stripped"),
                           **cap_extra)
        except Exception as exc:
            why = (e8_evidence.clip(f"bracket rails unmeasurable ({type(exc).__name__}: {exc}",
                                    200) + "); deferred")
            doc["skipped"].append({"window": name, "why": why})
            with contextlib.suppress(Exception):
                decided.note(name, e8_evidence.DEFERRED, e8_evidence.R_RISK_UNMEASURABLE, why,
                             risk_usd=risk_usd)
            log(f"[{name}] DEFERRED: {why}")
            continue
        if rail_skip is not None:
            rail = str(rail_skip["rail"])
            skip = {"window": name, **rail_skip, "missed_growth_risk_usd": round(risk_usd, 2)}
            doc["skipped"].append(skip)
            _record({"at": now.isoformat(timespec="seconds"), **skip,
                     "status": "RAIL_BLOCKED", "risk_frac": frac, "armed": bool(armed),
                     "levels": {k: {f: float(spec[k][f]) for f in ("price", "sl", "tp")}
                                for k in sized}})
            state["windows"][name] = {"placed_at": now.isoformat(timespec="seconds"),
                                      "placed_hour": hour, "hi": due["hi"], "lo": due["lo"],
                                      "orders": {}, "position_id": None, "shadow": not armed,
                                      "skipped": rail, "why": skip["why"]}
            with contextlib.suppress(Exception):
                decided.note(name, e8_evidence.SKIPPED, str(rail_skip["reason"]),
                             str(skip["why"]), risk_usd=risk_usd)
            log(f"[{name}] SKIPPED: {skip['why']}; MISSED GROWTH ({rail}): the window's "
                f"{risk_usd:.0f} USD of certified risk is not deployed")
            continue
        window_risk_usd = max(leg_risk.values()) if leg_risk else risk_usd
        shrunk_by: dict[str, dict[str, Any]] = {}
        for cut_row in cuts:
            # MISSED GROWTH (GROWTH_GOVERNANCE Rule 1), two-sided: the risk each cut withheld is
            # journalled; what the smaller leg saved is UNMEASURED (published_e8_gold_lines).
            shrink = {"window": name, "rail": cut_row["rail"], "reason": cut_row["reason"],
                      "why": cut_row["why"] + "; sent smaller, not skipped",
                      "lots": {k: v[0] for k, v in sized.items()},
                      "unshrunk_lots": cut_row["unshrunk_lots"],
                      "risk_usd": round(window_risk_usd, 2),
                      "certified_risk_usd": round(risk_usd, 2),
                      "missed_growth_risk_usd": round(cut_row["withheld"], 2),
                      **{k: v for k, v in cut_row.items()
                         if k not in ("rail", "reason", "why", "unshrunk_lots", "withheld")}}
            doc.setdefault("shrunk", []).append(shrink)
            _record({"at": now.isoformat(timespec="seconds"), **shrink, "status": "RAIL_SHRUNK",
                     "risk_frac": frac, "armed": bool(armed)})
            log(f"[{name}] SHRUNK: {shrink['why']}; MISSED GROWTH ({cut_row['rail']}): "
                f"{cut_row['withheld']:.0f} USD of risk withheld")
            for k, lot in cut_row["unshrunk_lots"].items():
                shrunk_by.setdefault(k, {"unshrunk_lot": lot, "by": []})["by"].append(
                    cut_row["reason"])
        committed = (committed or 0.0) + window_risk_usd
        legs: dict[str, dict] = {}
        failed: dict[str, dict] = {}
        for side in ("buy_stop", "sell_stop"):
            if side == blocked:
                why = (f"open XAU position(s) {', '.join(str(p.get('id')) for p in xau_positions)}"
                       f" already lean {'long' if direction == 1 else 'short'}; this leg would "
                       f"trade against them, so it is skipped and the agreeing leg is placed")
                doc["skipped"].append({"window": name, "side": side, "why": why})
                log(f"[{name}] {side} skipped: {why}")
                continue
            s = spec[side]
            dist = abs(float(s["price"]) - float(s["sl"]))
            legal, why = leg_is_legal(side, float(s["price"]), float(bid), float(ask))
            if not legal:
                doc["skipped"].append({"window": name, "side": side, "why": why})
                log(f"[{name}] {side} not available: {why}")
                continue
            lot, basis = sized[side]
            row = {"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
                   "price": float(s["price"]), "sl": float(s["sl"]), "tp": float(s["tp"]),
                   "lot": lot, "stop_dist": round(dist, 2),
                   "risk_usd": round(leg_risk.get(side, risk_usd), 2),
                   "sizing": basis, "risk_frac": frac, "risk_source": frac_src,
                   "armed": bool(armed)}
            if side in shrunk_by:
                row["shrunk"] = shrunk_by[side]
            if not (lot > 0):
                row["status"] = "UNSIZEABLE"
                doc["skipped"].append(row)
                _record(row)
                continue
            if not armed:
                row["status"] = "WOULD_PLACE"
                log(f"[{name}] SHADOW would place {side} {lot} {SYMBOL} @ {s['price']:.2f} "
                    f"sl {s['sl']:.2f} tp {s['tp']:.2f} (risk {row['risk_usd']:.0f} USD)")
                _record(row)
                legs[side] = {"id": None, **{k: row[k] for k in ("price", "sl", "tp", "lot")}}
                continue
            try:
                oid = venue.place_stop(SYMBOL, "buy" if side == "buy_stop" else "sell", lot,
                                       price=float(s["price"]), stop=float(s["sl"]),
                                       take_profit=float(s["tp"]))
                row.update({"status": "SENT", "order_id": oid})
                legs[side] = {"id": oid, **{k: row[k] for k in ("price", "sl", "tp", "lot")}}
                log(f"[{name}] PLACED {side} {lot} {SYMBOL} @ {s['price']:.2f} sl {s['sl']:.2f} "
                    f"tp {s['tp']:.2f} -> order {oid}")
            except Exception as exc:
                row.update({"status": "REJECTED",
                            "why": e8_evidence.clip(f"{type(exc).__name__}: {exc}", 200)})
                log(f"[{name}] REJECTED {side}: {row['why']} (will retry while the window holds)")
                failed[side] = {**{k: row[k] for k in ("price", "sl", "tp", "lot", "risk_usd")},
                                "attempts": 1, "why": row["why"],
                                "first_at": row["at"]}
            if not _record(row):
                doc.setdefault("journal_write_failed", []).append(
                    {"window": name, "side": side, "order_id": row.get("order_id")})
        state["windows"][name] = {"placed_at": now.isoformat(timespec="seconds"),
                                  "placed_hour": hour, "hi": due["hi"], "lo": due["lo"],
                                  "orders": legs, "position_id": None, "shadow": not armed}
        if failed:
            state["windows"][name]["failed"] = failed
        if legs or failed:
            placed_this_pass.append(name)
        doc["placed"].append({"window": name, "legs": legs})
        try:
            outcome, reason, why, sent_lot = e8_evidence.window_outcome(
                legs, failed, armed=armed, unsizeable=any(
                    r.get("window") == name and r.get("status") == "UNSIZEABLE"
                    for r in doc["skipped"]))
            if cuts:
                # A shrunk window is PLACED (reason placed) with the rails that cut it named.
                why = f"{why}; shrunk by {', '.join(sorted({str(c['reason']) for c in cuts}))}"
            decided.note(name, outcome, reason, why, lot=sent_lot, risk_usd=risk_usd)
        except Exception as exc:
            log(f"[{name}] decision evidence not derived ({type(exc).__name__}: {exc})")

    # -------------------------------------------------------------- management
    try:
        open_orders = venue.orders(SYMBOL)
        open_ids = {int(o.get("id")) for o in open_orders if o.get("id") is not None}
    except Exception as exc:
        open_orders = []
        open_ids = set()
        doc["orders_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
    filled: dict[int, int] = {}
    hist_rows: list[dict] = []
    try:
        hist = venue._api.get_all_orders(history=True, lookback_period="2D")
        hist_rows = hist.to_dict("records") if hasattr(hist, "to_dict") else list(hist)
        for o in hist_rows:
            if str(o.get("status") or "").lower() == "filled" and o.get("positionId"):
                filled[int(o["id"])] = int(o["positionId"])
    except Exception as exc:
        doc["history_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
    # THE SLIP IS MEASURED FROM THE LANE'S OWN STOP EXITS (prop/e8_gold_slip.py): each protective
    # stop that filled on a position our entry opened is journalled once, and E8_GOLD_SLIP.json is
    # re-measured from the journal. Never raises; nothing below reads it this pass.
    if hist_rows:
        try:
            exits = stop_exits_from_history(hist_rows, filled,
                                            own_entry_orders(_journal_rows(), state))
            doc["stop_exits_recorded"] = _record_stop_exits(exits, now=now)
        except Exception as exc:
            log(f"stop exits not derived ({type(exc).__name__}: {exc})")
    positions_ok = True
    try:
        venue_positions = venue.positions()
        xau_positions = gold_positions(venue_positions, iid)
        position_ids = {int(p["id"]) for p in xau_positions}
    except Exception as exc:
        positions_ok = False
        xau_positions = []
        position_ids = set()
        doc["positions_unreadable"] = e8_evidence.clip(f"{type(exc).__name__}: {exc}", 160)

    # -------------------------------------------------------------- stand-down cancels
    # THE GUARD'S REFUSAL REACHES WHAT ALREADY RESTS (see STAND_DOWN_CANCEL): a twin placed
    # before the verdict must not fill after it. Only on the guard's own verdict -- an unreadable
    # equity or guard is not a verdict -- and only when the order book was read this pass.
    if guard_decision is not None and not guard_decision.may_open \
            and "orders_unreadable" not in doc:
        gone = _cancel_on_stand_down(venue, state, doc, open_ids=open_ids, filled=filled,
                                     armed=armed, verdict=str(guard_decision.verdict.value))
        if gone:
            open_orders = [o for o in open_orders if o.get("id") is None
                           or int(o["id"]) not in gone]
            open_ids -= gone

    # -------------------------------------------------------------- dropped legs
    if any(w.get("failed") for w in (state.get("windows") or {}).values()):
        _retry_failed_legs(venue, state, doc, hour=hour, now=now, open_orders=open_orders,
                           orders_ok="orders_unreadable" not in doc, filled=filled,
                           xau_positions=xau_positions, positions_ok=positions_ok,
                           stood_down=stood_down, armed=armed, hist_rows=hist_rows,
                           history_ok="history_unreadable" not in doc, instrument_id=iid,
                           decided=decided)
        open_ids = {int(o.get("id")) for o in open_orders if o.get("id") is not None}

    # The decisions are written AFTER every placement and every re-send of a dropped leg this
    # pass, so a write that fails or hangs on the disk has no order left to delay, and a re-send
    # is on the same row set as the window it belongs to; it never raises (e8_evidence).
    doc["decisions"] = decided.rows
    doc["decisions_recorded"] = len(e8_evidence.record_decisions(
        decided, state, now=now, server_date=today, account=account, armed=armed, host=host,
        symbol=SYMBOL, log=log))

    # OUR OWN ORDERS AND POSITIONS, RE-DERIVED FROM THE VENUE EVERY PASS -- so a rollover (or a
    # lost state file) can neither orphan a position from management nor leave a GTC leg resting.
    own = own_entry_orders(_journal_rows(), state)
    if positions_ok and iid:
        for act in readopt_positions(state, filled, position_ids, own):
            log(f"[{act['window']}] RE-ADOPTED position {act['position_id']} "
                f"(opened by our order {act['order_id']})")
            act["ok"] = True
            doc["actions"].append(act)
        state["carried"] = {n: w for n, w in (state.get("carried") or {}).items()
                            if int(w.get("position_id") or 0) in position_ids}
    for oid in stale_entry_orders(state, open_ids, own):
        act = {"act": "stale_cancel", "window": str(own[oid].get("window")), "order_id": oid}
        try:
            act["ok"] = bool(venue.cancel(int(oid)))
            log(f"[{act['window']}] stale_cancel: our GTC entry order {oid} outlived its day; "
                f"cancelled")
        except Exception as exc:
            act["ok"] = False
            act["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{act['window']}] stale_cancel FAILED: {act['why']}")
        doc["actions"].append(act)

    # The Fusion gold book and this E8 port are the same bracket strategy.  Both therefore use
    # the same measured stop ratchet.  Until this block existed E8 left every winner at its
    # opening stop until the fixed target or close hour, recreating the exact giveback path fixed
    # in Fusion.  Broker stop orders are re-read on every pass; local state advances only after
    # the venue acknowledges the PATCH.
    order_by_id = {int(o["id"]): o for o in open_orders if o.get("id") is not None}
    _info = getattr(mt5, "symbol_info", lambda _s: None)(SYMBOL)
    stop_step = float(getattr(_info, "trade_tick_size", 0.0) or 0.0) or STOP_STEP
    for p in xau_positions:
        mapped = _window_for_position(state, int(p["id"]))
        stop_order = order_by_id.get(int(p.get("stopLossId") or 0))
        current_stop = float((stop_order or {}).get("stopPrice") or 0.0)
        if mapped is None or not (current_stop > 0):
            continue
        name, w = mapped
        refused = w.get("stop_refusals") or {}
        if int(refused.get("count") or 0) >= MAX_STOP_REFUSALS:
            # BOUNDED: no more stop moves for this position (see MAX_STOP_REFUSALS).
            verdict, why = stop_refusal_response(
                p, w, bid=float(bid), ask=float(ask),
                cost_per_unit=E8_ROUND_TRIP_PER_PRICE_UNIT)
            if verdict == "close":
                act = {"act": "stop_refused_close", "window": name, "position_id": int(p["id"]),
                       "why": why, "ok": False}
                try:
                    if armed or not w.get("shadow", False):
                        act["ok"] = bool(venue.close(int(p["id"])))
                    else:
                        act.update({"ok": True, "shadow": True})
                    if act["ok"]:
                        w["closed"] = True
                    else:
                        act["why"] += "; the venue did not acknowledge the close"
                except Exception as exc:
                    act["why"] += f"; close FAILED: {type(exc).__name__}: {exc}"[:160]
                log(f"[{name}] ALERT position {p['id']}: {act['why']}")
                doc.setdefault("alerts", []).append(act["why"])
                doc["actions"].append(act)
            elif not refused.get("held"):
                refused["held"] = True
                log(f"[{name}] ALERT position {p['id']}: {why}")
                doc.setdefault("alerts", []).append(f"position {p['id']}: {why}")
                doc["actions"].append({"act": "stop_refused_hold", "window": name,
                                       "position_id": int(p["id"]), "why": why, "ok": True})
            continue
        decision = trail_decision(
            p, w, df, current_stop,
            cost_per_unit=E8_ROUND_TRIP_PER_PRICE_UNIT,
            spread=max(0.0, float(ask) - float(bid)))
        # ANY TIGHTENING THE VENUE CAN REPRESENT IS SENT (2026-09-29), trail or break-even; the
        # 0.05R floor skipped real protection to save a request that costs no spread.
        if decision is None or not decision.moves or not _pm.tightens_by_min_step(
                side=1 if str(p.get("side") or "").lower() == "buy" else -1,
                new_stop=float(decision.new_stop), current_stop=current_stop, step=stop_step):
            continue
        action = {"act": "ratchet_stop", "window": name, "position_id": int(p["id"]),
                  "before": current_stop, "after": float(decision.new_stop),
                  "improvement_r": round(decision.improvement_r, 6), "ok": False}
        # THE LEVEL MUST STILL BE A STOP WHEN IT ARRIVES, and on this venue that is not free.
        # Measured here on 2026-09-24: the first ratchet this lane ever sent moved position
        # 360287970193246861's stop from 4303.25 to 4259.78 while the market was at 4283.5.  The
        # venue took the modification, the buy stop was already through its trigger, and it
        # filled at market -- 4283.91, 24.13 points and 386.08 USD worse than the level the desk
        # had just proven protected more.  `ratchet` cannot see that: it compares the candidate
        # to the current stop, never to the market.  MetaTrader rejects such a request; this
        # venue executes it, so the check has to happen before the send.
        #
        # `bid`/`ask` are this pass's quote, read seconds earlier at the top of `run`.  Re-quoting
        # per position would be a second venue call per pass on an API that has already returned
        # 429 to this lane today, and a quote a few seconds stale can only make this refuse a
        # borderline level -- which leaves the account's existing stop in place, the safe error.
        _side = 1 if str(p.get("side") or "").lower() == "buy" else -1
        _rests, _why_rest = _pm.stop_rests_at_venue(
            stop=float(decision.new_stop), side=_side, bid=float(bid), ask=float(ask))
        if not _rests:
            action["act"] = "ratchet_refused"
            action["why"] = _why_rest
            log(f"[{name}] stop ratchet REFUSED: {_why_rest}")
            doc["actions"].append(action)
            continue
        try:
            if armed or not w.get("shadow", False):
                action["ok"] = bool(venue.modify_stop(int(p["id"]), float(decision.new_stop)))
            else:
                action["ok"] = True
                action["shadow"] = True
            if action["ok"]:
                w.pop("stop_refusals", None)
                log(f"[{name}] {'SHADOW would ratchet' if action.get('shadow') else 'RATCHET'} "
                    f"position {p['id']} stop {current_stop:.2f} -> "
                    f"{float(decision.new_stop):.2f}; {decision.reason}")
            else:
                action["why"] = "venue did not acknowledge the stop modification"
                log(f"[{name}] stop ratchet NOT acknowledged; broker state remains authoritative")
        except Exception as exc:
            action["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{name}] stop ratchet FAILED: {action['why']}")
        if not action["ok"]:
            count = int((w.get("stop_refusals") or {}).get("count") or 0) + 1
            w["stop_refusals"] = {"count": count, "last_at": now.isoformat(timespec="seconds"),
                                  "last_why": action.get("why")}
            action["refusals"] = count
            if count >= MAX_STOP_REFUSALS:
                log(f"[{name}] ALERT position {p['id']}: the venue refused {count} stop moves in "
                    f"a row; no further moves are sent (close if beyond the break-even trigger, "
                    f"else hold the resting stop)")
                doc.setdefault("alerts", []).append(
                    f"position {p['id']}: {count} consecutive stop moves refused by the venue")
        doc["actions"].append(action)
    # Positions carried from a previous day are closed at the close hour like today's.
    for name, w in list((state.get("carried") or {}).items()):
        state["windows"].setdefault(f"carried:{name}",
                                    {"orders": {}, "position_id": w.get("position_id")})
    for act in manage_actions(state, hour, open_ids, filled, position_ids):
        w = state["windows"].get(act["window"]) or {}
        kind = act["act"]
        try:
            if kind == "record_position":
                w["position_id"] = act["position_id"]
                log(f"[{act['window']}] {act['side']} filled -> position {act['position_id']}")
            elif kind in ("oco_cancel", "ttl_cancel", "eod_cancel"):
                # THE VENUE'S ANSWER IS READ (2026-09-30). `cancel` and `close` return the
                # acknowledgement; both were discarded and the action logged as done, so a leg
                # the venue refused to cancel stayed resting while the pass reported it gone.
                if (armed or not w.get("shadow", False)) and \
                        not venue.cancel(int(act["order_id"])):
                    raise RuntimeError(f"venue did not acknowledge cancel of order "
                                       f"{act['order_id']}; it may still be resting")
                log(f"[{act['window']}] {kind}: order {act['order_id']} cancelled")
            elif kind == "close":
                if (armed or not w.get("shadow", False)) and \
                        not venue.close(int(act["position_id"])):
                    raise RuntimeError(f"venue did not acknowledge close of position "
                                       f"{act['position_id']}; it may still be open")
                w["closed"] = True
                log(f"[{act['window']}] CLOSE position {act['position_id']} at the close hour")
            act["ok"] = True
        except Exception as exc:
            act["ok"] = False
            act["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{act['window']}] {kind} FAILED: {act['why']}")
        doc["actions"].append(act)
    state["windows"] = {n: w for n, w in state["windows"].items() if not n.startswith("carried:")}

    # THE SLIP IS PUBLISHED ON EVERY PASS, AFTER PLACEMENT (coordinator, hourly pass 15): overall
    # and per window, in points, into E8_GOLD_SLIP.json and this report. `publish_slip` never
    # raises; a failure publishes UNMEASURED and the guard keeps DEFAULT_SLIP_POINTS.
    doc["slip"] = publish_slip(now=now)
    doc.setdefault("status", "OK")
    try:
        beat_extra: dict[str, Any] = {
            "server_time": doc.get("server_time"), "hour": doc.get("hour"),
            "guard": (doc.get("guard_decision") or {}).get("verdict") or doc.get("guard"),
            "open_xau_positions": len(xau_positions), "decisions": len(decided.rows)}
    except Exception as exc:
        beat_extra = {"extra_unreadable": f"{type(exc).__name__}: {exc}"[:160]}
    doc["heartbeat"] = e8_evidence.write_heartbeat(
        str(doc["status"]), at=now, armed=armed, account=account, host=host, log=log,
        extra=beat_extra)
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1, default=str), encoding="utf-8")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        doc["state"] = state
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        log(f"state/report write failed: {exc}")
    return doc


def _retry_failed_legs(venue: Any, state: dict, doc: dict, *, hour: float, now: datetime,
                       open_orders: list[dict], orders_ok: bool, filled: dict[int, int],
                       xau_positions: list[dict], positions_ok: bool, stood_down: bool,
                       armed: bool, hist_rows: list[dict], history_ok: bool,
                       instrument_id: int,
                       decided: e8_evidence.Decisions | None = None) -> None:
    """Re-send the legs `retry_decisions` says still belong to a live window. Mutates `state`,
    appends to `doc["actions"]` and to `open_orders` (so the rest of the pass sees the new leg).

    EVERY OUTCOME IS EVIDENCE (prop/e8_evidence.py, v2): a re-send or an adopted landed send is
    a PLACED row, an abandoned leg a row of its own (`abandon_reason`), a re-send the venue
    refused again a `venue_rejected` deferral. Noted into `decided`, which never raises and is
    read by nothing that sends.

    Fails CLOSED: nothing is re-sent on a disarmed pass, with the order book, the order history
    or the position book unreadable (a duplicate or a self-hedge is worse than a missing leg), or
    while the guard stands down. A send that errored may still have LANDED -- resting, or already
    filled and closed back to the level -- so before any re-send the leg is looked for as a
    resting order, then as a filled order in the history, then as a position on its side opened
    since the failed send.
    """
    blind = [why for why, bad in (("the pass is disarmed", not armed),
                                  ("the guard stands down", stood_down),
                                  ("the order book is unreadable", not orders_ok),
                                  ("the position book is unreadable", not positions_ok),
                                  ("the order history is unreadable", not history_ok),
                                  ("the gold instrument id is unknown", not instrument_id))
             if bad]
    journal = _journal_read()
    if journal is None:
        blind.append("the intents journal is missing or unreadable, so this lane's own order "
                      "ids cannot be told apart from the lost send")
    if blind:
        waiting = [f"{n}/{side}" for n, w in (state.get("windows") or {}).items()
                   for side in (w.get("failed") or {})]
        doc["retry_skipped"] = {"why": blind, "legs": waiting}
        log(f"dropped legs {waiting} not re-sent this pass: {'; '.join(blind)}")
        return
    try:
        bid, ask = venue.quote(SYMBOL)
    except Exception as exc:
        doc["retry_quote_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
        return
    direction = book_direction(xau_positions)
    if direction is None:
        return
    blocked = OPPOSING_LEG.get(direction)
    known = {int(leg["id"]) for bucket in ("windows", "carried")
             for w in (state.get(bucket) or {}).values()
             for leg in (w.get("orders") or {}).values() if leg.get("id") is not None}
    # Every id the intents journal says this lane sent -- yesterday's legs included, which have
    # left the state at the rollover but still sit in the venue's two-day history.
    jrows = journal or []
    known |= set(own_entry_orders(jrows, state))
    # A position a block already stood aside for, and the order that opened it, are known too.
    known |= {int(r["order_id"]) for r in jrows
              if r.get("status") == "RAIL_BLOCKED" and r.get("order_id") is not None}
    skew = venue_clock_skew_ms(jrows, [*open_orders, *hist_rows])
    try:
        venue_min = float(venue.min_lot(SYMBOL))
    except Exception:
        venue_min = 0.0
    for dec in retry_decisions(state, hour, float(bid), float(ask), filled, blocked):
        name, side, leg = dec["window"], dec["side"], dec["leg"]
        w = state["windows"][name]
        act = {"act": f"leg_{dec['act']}", "window": name, "side": side,
               "attempts": int(leg.get("attempts") or 0)}
        if dec["act"] == "hold":
            continue
        if dec["act"] == "abandon":
            w["failed"].pop(side, None)
            w.setdefault("abandoned", {})[side] = {**leg, "why": dec["why"]}
            act["why"] = dec["why"]
            log(f"[{name}] {side} dropped leg abandoned: {dec['why']}")
            doc["actions"].append(act)
            with contextlib.suppress(Exception):
                if decided is not None:
                    decided.note(name, e8_evidence.SKIPPED,
                                 e8_evidence.abandon_reason(dec["why"], w),
                                 f"{side} abandoned: {dec['why']}", lot=leg.get("lot"),
                                 risk_usd=leg.get("risk_usd"))
            continue
        levels = {k: leg[k] for k in ("price", "sl", "tp", "lot")}
        done = [o for o in hist_rows if str(o.get("status") or "").lower() == "filled"]
        # The send time on the VENUE's clock, and the size the venue actually sends (the adapter
        # floors every lot at the venue minimum), so neither a skewed box nor a small lot can
        # hide a send that landed.
        sent_at = _iso_ms(leg.get("first_at"))
        since = (sent_at + skew if skew is not None
                 # the matcher allows LEG_MATCH_WINDOW_MS of slack below `since`; none of it
                 # may reach back past the rollover
                 else max(sent_at - UNMEASURED_SKEW_MS,
                          last_rollover_ms(sent_at) + LEG_MATCH_WINDOW_MS))
        oid = None
        for book in (open_orders, done):
            oid = oid or matching_resting_order(book, side, float(leg["price"]), known,
                                                lot=max(float(leg["lot"]), venue_min),
                                                instrument_id=int(instrument_id),
                                                since_ms=since)
        pos_id = None if oid is not None else position_since_failure(
            xau_positions, side, leg.get("first_at"), state, filled)
        if pos_id is not None:
            why = ("a position on this side opened after the failed send and no window owns it: "
                   "it may be that send, so the leg is not sent again")
            # MISSED GROWTH (GROWTH_GOVERNANCE Rule 1): if that position is NOT our send, this
            # veto forgoes the leg's whole certified risk. Record what it costs every time.
            missed = leg.get("risk_usd")
            if missed is None:
                stop = abs(float(leg["price"]) - float(leg["sl"]))
                missed = float(leg["lot"]) * stop * XAU_OZ_PER_LOT
            w["failed"].pop(side, None)
            w.setdefault("abandoned", {})[side] = {**leg, "why": why}
            doc["actions"].append({**act, "act": "leg_abandon", "why": why,
                                   "rail": UNOWNED_BLOCK_RAIL,
                                   "missed_growth_risk_usd": round(float(missed), 2)})
            _record({"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
                     **levels, "status": "RAIL_BLOCKED", "rail": UNOWNED_BLOCK_RAIL,
                     "missed_growth_risk_usd": round(float(missed), 2),
                     "position_id": int(pos_id),
                     "order_id": next((int(o) for o, p in filled.items() if int(p) == pos_id),
                                      None),
                     "retry_of": leg.get("first_at")})
            log(f"[{name}] {side} dropped leg abandoned: {why}; MISSED GROWTH "
                f"({UNOWNED_BLOCK_RAIL}): the leg's {float(missed):.0f} USD of certified risk "
                "is not deployed")
            with contextlib.suppress(Exception):
                if decided is not None:
                    decided.note(name, e8_evidence.SKIPPED, e8_evidence.R_UNOWNED_POSITION,
                                 f"{side} abandoned: {why}", lot=leg.get("lot"), risk_usd=missed)
            continue
        row = {"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
               **levels, "armed": True, "retry_of": leg.get("first_at")}
        if oid is not None:
            row.update({"status": "SENT", "order_id": oid, "adopted": True})
            log(f"[{name}] {side} the failed send had landed: adopted order {oid}")
        else:
            try:
                oid = venue.place_stop(SYMBOL, "buy" if side == "buy_stop" else "sell",
                                       float(leg["lot"]), price=float(leg["price"]),
                                       stop=float(leg["sl"]), take_profit=float(leg["tp"]))
                row.update({"status": "SENT", "order_id": oid})
                log(f"[{name}] RE-PLACED {side} {leg['lot']} {SYMBOL} @ {leg['price']:.2f} "
                    f"-> order {oid} (attempt {int(leg.get('attempts') or 0) + 1})")
            except Exception as exc:
                leg["attempts"] = int(leg.get("attempts") or 0) + 1
                leg["why"] = e8_evidence.clip(f"{type(exc).__name__}: {exc}", 200)
                row.update({"status": "REJECTED", "why": leg["why"]})
                act.update({"ok": False, "why": leg["why"]})
                log(f"[{name}] {side} retry REJECTED: {leg['why']}")
                _record(row)
                doc["actions"].append(act)
                with contextlib.suppress(Exception):
                    if decided is not None:
                        decided.note(name, e8_evidence.DEFERRED, e8_evidence.R_VENUE_REJECTED,
                                     f"{side} re-send refused: {leg['why']}", lot=leg.get("lot"),
                                     risk_usd=leg.get("risk_usd"))
                continue
        _record(row)
        w.setdefault("orders", {})[side] = {"id": int(oid), **levels}
        w["failed"].pop(side, None)
        known.add(int(oid))
        open_orders.append({"id": int(oid), "side": "buy" if side == "buy_stop" else "sell",
                            "stopPrice": float(leg["price"])})
        act.update({"ok": True, "order_id": int(oid), "adopted": bool(row.get("adopted"))})
        doc["actions"].append(act)
        with contextlib.suppress(Exception):
            if decided is not None:
                decided.note(name, e8_evidence.PLACED, e8_evidence.R_PLACED,
                             (f"{side}: the failed send had landed, adopted order {oid}"
                              if row.get("adopted") else f"{side} re-sent -> order {oid}"),
                             lot=leg.get("lot"), risk_usd=leg.get("risk_usd"))
    for w in (state.get("windows") or {}).values():
        if "failed" in w and not w["failed"]:
            del w["failed"]


def connect_terminal(mt5: Any, attach: Any, path: str, *,
                     waits: tuple[float, ...] = MT5_RETRY_WAITS_S,
                     sleep: Any = None) -> tuple[bool, int]:
    """Attach to the terminal, re-initialising it on failure, until it answers a gold tick.

    NO IPC CONNECTION COST ~70 MINUTES ON 2026-09-30. The pass tried `attach_or_initialize`
    once and, on a dead IPC handle, gave up for five minutes -- then did the same again, so a
    terminal that had merely dropped its pipe stayed "unavailable" until something else reset
    it. `terminal_info()` can also answer on a handle whose data calls fail, so success here
    means a real XAUUSD tick, not a handshake. Between attempts the stale handle is shut down so
    `initialize` builds a fresh one. Returns (connected, attempts used).
    """
    pause = sleep or time.sleep
    for n, wait in enumerate(waits, start=1):
        if wait > 0:
            pause(wait)
        try:
            if attach(mt5, path=path, timeout=15000) and mt5.symbol_info_tick(SYMBOL) is not None:
                return True, n
        except Exception as exc:
            log(f"MT5 attach attempt {n} raised {type(exc).__name__}: {exc}")
        log(f"MT5 attach attempt {n}/{len(waits)} failed: {mt5.last_error()}")
        with contextlib.suppress(Exception):
            mt5.shutdown()
    return False, len(waits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--armed", action="store_true", help="arm this pass regardless of the marker")
    args = ap.parse_args(argv)
    armed = bool(args.armed or ARMED_MARKER.exists())
    try:
        import MetaTrader5 as mt5
        from mt5desk.config import terminal_path
        from research.mt5_session import attach_or_initialize
        ok, _tries = connect_terminal(mt5, attach_or_initialize, terminal_path())
        if not ok:
            log(f"MT5 unavailable after {_tries} attempts: {mt5.last_error()}")
            _failed_pass("MT5_UNAVAILABLE", armed=armed)
            return 1
    except Exception as exc:
        log(f"MetaTrader5 unavailable ({type(exc).__name__}: {exc})")
        _failed_pass("MT5_UNAVAILABLE", armed=armed)
        return 1
    try:
        from prop.tradelocker_venue import TradeLockerVenue, load_credentials
        venue = TradeLockerVenue(creds=load_credentials()).connect()
    except Exception as exc:
        log(f"venue unavailable ({type(exc).__name__}: {exc})")
        _failed_pass("VENUE_UNAVAILABLE", armed=armed)
        mt5.shutdown()
        return 1
    try:
        doc = run(venue, mt5, armed=armed)
        if doc.get("status") == "NO_BARS":
            # The pipe can die between the attach and the first data call. NO_BARS returns
            # before any state is touched, so one reconnect and a second pass are safe.
            ok, _tries = connect_terminal(mt5, attach_or_initialize, terminal_path(),
                                          waits=MT5_RETRY_WAITS_S[1:])
            if ok:
                doc = run(venue, mt5, armed=armed)
    finally:
        mt5.shutdown()
    log(f"e8 gold: {'ARMED' if armed else 'SHADOW'} hour={doc.get('hour')} "
        f"equity={doc.get('equity')} placed={len(doc.get('placed') or [])} "
        f"actions={len(doc.get('actions') or [])} skipped={len(doc.get('skipped') or [])} "
        f"status={doc.get('status')}")
    return 0


def _failed_pass(status: str, *, armed: bool) -> None:
    """Publish connection failure without altering durable window/order state."""
    at = datetime.now(UTC)
    e8_evidence.bind_account(e8_evidence.UNMEASURED)
    beat = e8_evidence.write_heartbeat(status, at=at, armed=armed, log=log)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text(json.dumps({"at": at.isoformat(),
                                     "status": status, "armed": armed,
                                     "placed": [], "actions": [], "skipped": [],
                                     "host": (beat or {}).get("host"),
                                     "why": "connection failed; no placement evaluated"}), "utf-8")
    temporary.replace(OUT)


if __name__ == "__main__":
    raise SystemExit(main())
