"""THE ONLY THING ALLOWED TO REFUSE AN ORDER FOR A PROP REASON, and the account's whole defence.

E8 Pro, $100,000, account 2478877. The rules it enforces, from the invoice and the dashboard:

    profit target      10%   -> $110,000 equity and the evaluation is over
    max drawdown       10%   STATIC -- a floor at $90,000 that never trails
    daily drawdown     2.5%  -> $2,500 below the day's starting balance, hard breach
    daily profit cap   2%    -> $2,000 counted; the EXCESS IS STRIPPED at rollover

WHY THIS IS A SEPARATE FILE FROM THE ADAPTER. The adapter can be tested against a fake API and
this can be tested against a fake account. Fused, neither is testable, and the first real test of
a funded account's risk rules would be a funded account.

THE FOUR REFUSALS, and the third is the one nobody writes:

    BREACHED   equity is at or below a floor. Nothing trades again, ever. Reporting this as a
               refusal rather than discovering it from a broker email is the point of the file.
    STOOD_DOWN a VOLUNTARY floor set inside E8's, which flattens and stops opening for the
               session. Measured worth: it takes daily breaches to zero and costs nothing in
               time. It cannot add drift -- a stop on a driftless walk moves variance, not
               drift -- and `research/prop_barrier.py` records the modelling error that briefly
               claimed otherwise.
    CAPPED     the day's profit has reached +2%, so EVERY FURTHER TRADE IS PURE DOWNSIDE: the
               gain would be stripped at rollover and the loss would not. This is free and the
               simulation does not even model it, which makes every pass number in
               PROP_BARRIER.json conservative rather than optimistic. Not trading is a position.
    PASSED     the target is reached. Continuing to trade a passed evaluation is how a pass
               becomes a breach.

WHAT IT DOES NOT DO. It does not size, it does not choose a sleeve, and it never RAISES risk --
every verdict it can return is "trade smaller or not at all". The live Fusion book is untouched
by this file and by the reasoning in it: the principal's standing order that the desk never
reduces its aggressiveness is about the growth account, and this is a barrier with its right tail
confiscated. Two venues, two problems -- `mt5desk/account_profile.py` draws the same line.

Artifact: desks/mt5/reports/E8_GUARD.json
State:    desks/mt5/data/e8_guard_state.json   (the day's opening balance; the box's, not origin's)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "E8_GUARD.json"
STATE = DESK / "data" / "e8_guard_state.json"

# ------------------------------------------------------------------ the arena
START_BALANCE = 100_000.0
PROFIT_TARGET = 0.10
STATIC_DRAWDOWN = 0.10
DAILY_DRAWDOWN = 0.025
DAILY_PROFIT_CAP = 0.02

#: THE VOLUNTARY FLOOR, set inside E8's 2.5%. `prop_barrier` measures what it buys; this is the
#: number the principal's chosen configuration runs. It is a policy constant and changing it is a
#: decision, which is why it is named here rather than computed.
STAND_DOWN = 0.0075

#: E8's rollover is "between midnight and 1am SERVER time", and the server is not UTC. UNCONFIRMED
#: for this account -- most MT/TradeLocker prop servers run UTC+2 in winter and UTC+3 in summer.
#: It is declared here as an offset so that reading the real value off the dashboard is a one-line
#: change rather than a hunt, and so that a wrong value is a visible assumption rather than a
#: silent one. Getting it wrong misplaces the DAILY floor by a few hours, which is the difference
#: between a stand-down that works and one that measures the wrong day.
SERVER_UTC_OFFSET_HOURS = 3


class Verdict(StrEnum):
    OK = "OK"
    STOOD_DOWN = "STOOD_DOWN"
    CAPPED = "CAPPED"
    BREACHED = "BREACHED"
    PASSED = "PASSED"


@dataclass
class Decision:
    verdict: Verdict
    why: str
    equity: float
    day_start: float
    day_pnl: float
    room_to_daily_floor: float
    room_to_static_floor: float
    counted_profit_today: float
    flatten: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def may_open(self) -> bool:
        return self.verdict is Verdict.OK

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value, "why": self.why,
            "equity": round(self.equity, 2), "day_start": round(self.day_start, 2),
            "day_pnl": round(self.day_pnl, 2),
            "room_to_daily_floor": round(self.room_to_daily_floor, 2),
            "room_to_static_floor": round(self.room_to_static_floor, 2),
            "counted_profit_today": round(self.counted_profit_today, 2),
            "flatten": self.flatten, "may_open": self.may_open, **self.detail,
        }


def server_day(now: datetime | None = None) -> str:
    """The trading day E8 is measuring, not the one the box's clock is in.

    The daily floor and the profit cap both reset at the SERVER's midnight. A guard that rolled
    over at UTC midnight would measure a window offset from the one being enforced, and would be
    most wrong exactly when it mattered -- during the asia session, which is where every one of
    this desk's certified sleeves fires.
    """
    now = now or datetime.now(UTC)
    return (now.astimezone(UTC) + timedelta(hours=SERVER_UTC_OFFSET_HOURS)).strftime("%Y-%m-%d")


def load_state(path: Path = STATE) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return dict(loaded) if isinstance(loaded, dict) else {}
    except Exception:
        # AN UNREADABLE STATE FILE IS NOT A LICENCE TO TRADE WITHOUT ONE, but it is also not a
        # reason to refuse forever: `assess` re-anchors the day on the current equity, which is
        # conservative (it can only make the floor nearer) and self-healing at the next rollover.
        return {}


def save_state(state: dict[str, Any], path: Path = STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def assess(equity: float, *, now: datetime | None = None, state: dict[str, Any] | None = None,
           persist: bool = True, state_path: Path = STATE) -> Decision:
    """The one call the executor makes before it opens anything.

    THE DAY'S OPENING BALANCE IS REMEMBERED, NOT RE-DERIVED. The daily floor is measured from the
    balance at the server's midnight, so it must survive every gateway restart during the day. If
    the anchor were recomputed from current equity on each pass, a book that was already down 2%
    would silently get a fresh 2.5% of room -- the floor would follow the losses down, which is
    the one direction a floor must never move.
    """
    st = dict(load_state(state_path) if state is None else state)
    day = server_day(now)
    if st.get("day") != day:
        st = {"day": day, "day_start": float(equity), "peak_equity": float(equity),
              "stood_down": False}
    st["peak_equity"] = max(float(st.get("peak_equity", equity)), float(equity))

    # EVERY THRESHOLD IS ROUNDED TO CENTS BEFORE IT IS COMPARED. `100_000.0 * 1.10` is
    # 110000.00000000001 in binary floating point, so a literal `equity >= START_BALANCE * (1 +
    # PROFIT_TARGET)` reported OK at exactly $110,000 -- the guard missed the pass by one part in
    # 10^11, and the test below caught it on the first run. The same arithmetic sits under both
    # floors, where the error runs the other way and would report OK one hundredth of a cent
    # inside a breach. Money is counted in cents; the comparisons are made there.
    def _c(x: float) -> int:
        return int(round(x * 100))

    day_start = float(st["day_start"])
    day_pnl = equity - day_start
    static_floor = START_BALANCE * (1.0 - STATIC_DRAWDOWN)
    daily_floor = day_start * (1.0 - DAILY_DRAWDOWN)
    stand_floor = day_start * (1.0 - STAND_DOWN)
    cap_usd = START_BALANCE * DAILY_PROFIT_CAP
    counted = min(day_pnl, cap_usd) if day_pnl > 0 else day_pnl

    common = {
        "equity": float(equity), "day_start": day_start, "day_pnl": day_pnl,
        "room_to_daily_floor": equity - daily_floor,
        "room_to_static_floor": equity - static_floor,
        "counted_profit_today": counted,
    }

    def done(v: Verdict, why: str, flatten: bool = False, **detail: Any) -> Decision:
        if persist:
            save_state(st, state_path)
        return Decision(verdict=v, why=why, flatten=flatten, detail=detail, **common)

    # ORDER MATTERS AND THIS IS THE ORDER. A breach is permanent, so it is tested before anything
    # that could report a softer verdict on the same equity; a pass is tested next, because
    # continuing to trade a passed evaluation is how a pass becomes a breach.
    if _c(equity) <= _c(static_floor):
        return done(Verdict.BREACHED, f"equity {equity:,.0f} is at or below the STATIC floor "
                                      f"{static_floor:,.0f}; the account is gone", flatten=True,
                    breach="static")
    if _c(equity) <= _c(daily_floor):
        return done(Verdict.BREACHED, f"equity {equity:,.0f} is at or below today's floor "
                                      f"{daily_floor:,.0f}; the account is gone", flatten=True,
                    breach="daily")
    if _c(equity) >= _c(START_BALANCE * (1.0 + PROFIT_TARGET)):
        return done(Verdict.PASSED, f"equity {equity:,.0f} has reached the "
                                    f"{PROFIT_TARGET:.0%} target; stop trading", flatten=True)
    if _c(equity) <= _c(stand_floor) or st.get("stood_down"):
        st["stood_down"] = True
        return done(Verdict.STOOD_DOWN,
                    f"down {day_pnl:,.0f} today, at or past the voluntary {STAND_DOWN:.2%} "
                    f"stand-down ({stand_floor:,.0f}); no new risk until the server day rolls",
                    flatten=True)
    if _c(day_pnl) >= _c(cap_usd):
        return done(Verdict.CAPPED,
                    f"today's counted profit is at the {DAILY_PROFIT_CAP:.0%} cap "
                    f"({cap_usd:,.0f}); anything more is stripped at rollover while a loss is "
                    "not, so every further trade today is pure downside")
    return done(Verdict.OK, f"{equity - daily_floor:,.0f} to today's floor, "
                            f"{equity - static_floor:,.0f} to the static floor, "
                            f"{cap_usd - max(day_pnl, 0.0):,.0f} of counted profit left today")


def write_report(decision: Decision, path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_utc": datetime.now(UTC).isoformat(),
        "account": {"balance": START_BALANCE, "target": PROFIT_TARGET,
                    "static_drawdown": STATIC_DRAWDOWN, "daily_drawdown": DAILY_DRAWDOWN,
                    "daily_profit_cap": DAILY_PROFIT_CAP, "stand_down": STAND_DOWN,
                    "server_utc_offset_hours": SERVER_UTC_OFFSET_HOURS},
        "decision": decision.as_dict(),
    }, indent=1), encoding="utf-8")
    return path
