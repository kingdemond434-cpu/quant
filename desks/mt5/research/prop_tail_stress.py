"""TAIL-SCENARIO STRESS OF THE LIVE PROP BOOK (IDEA_QUEUE row 13, idea pass 20). REPORT ONLY.

What the live book loses if a tail event lands on it, per account, against each account's own
floors. Nothing here sends, sizes or arms anything, and it writes no config. Its only output is
a JSON report.

THE BOOK (as stated by the principal for pass 20; not read from the box):
    E8 Pro           gold_asia, 0.006 of equity at risk per leg
    FTMO 2-Step       gold_asia, 0.009 per leg, a manual SAME-DIRECTION follower of E8
    Fusion (EUR)     the venue minimum lot (0.01) per leg: gold_asia, plus the AUDCHF sleeve
                     for the CHF shock

THE FLOORS:
    E8      static floor at 90% of start (STATIC_DRAWDOWN); daily 2.5% of the day's start,
            floating P&L included. Both are parsed with `ast` from prop/e8_guard.py, which is
            never imported.
    FTMO    5% daily and 10% max loss of the start balance. These are public rule figures.
            There is no FTMO module in the repo to parse them from.
    Fusion  deadman EQUITY_FLOOR_EUR and DAILY_LOSS_PCT, parsed from proposals/fusion_deadman.py.
            Equity comes from data/account_state.json (measured, stamped).

THE SCENARIOS. Every magnitude says where it came from:
    snb_2015       EXTERNAL. The repo's bars start in 2018. The figures are EURCHF on
                   2015-01-15: open about 1.2010, low about 0.85 (-29.2%), and stops filled near
                   1.03 (-14.4%). The move is transplanted as a percent gap through every open
                   leg, filled at the gap price. The AUDCHF leg on Fusion takes the same percent.
    flash_crash    REPO BARS. The largest one-bar adverse excursion in XAUUSD H1 (2018-2026),
                   open to extreme, in ATR multiples. It is scaled to today's ATR, and the fill
                   is at the extreme (liquidity vacuum).
    weekend_gap    REPO BARS. The largest Friday-close to Monday-open XAUUSD gap, as a percent of
                   price, scaled to the last price. It assumes a position was held over the
                   weekend (a force-close failure); otherwise the book is flat at the weekend.
    replay_worst   REPO BARS. The worst single day of the gold_asia replay (`replay_gold_asia`),
                   with the OCO-fail variant and the slip tail on every stop exit.

THE SLIP TAIL. books.sim_v3 does not exist on this branch, so its empirical slip tail cannot be
read. The tail used here is the one measured E8 observation: 24.13 points on one leg
(2026-09-24, mt5desk/position_manager.py). It is charged on every stop exit until there are 20 or
more measured stop exits, after which the tail must be re-estimated. Status: N_STOP_EXITS_MEASURED
= 1. The tail is a placeholder, not a distribution.

STATE. The E8 and FTMO state files do not exist in the repo, so each account is stressed from its
start balance (full room). The breach against CURRENT room is UNMEASURED, and the report says so
rather than writing 0 or OK.

    python research/prop_tail_stress.py                  -> reports/PROP_TAIL_STRESS.json
    python research/prop_tail_stress.py --out PATH --legs 2

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `prop_tail_stress` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import prop_tail_stress as M; M.main()"
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.decision_core import (  # noqa: E402  (pure module, read only)
    ATR_N,
    CLOSE_HOUR,
    GOLD_WINDOWS,
    bracket_spec,
)

UNMEASURED = "UNMEASURED"
OUT = DESK / "reports" / "PROP_TAIL_STRESS.json"
BARS = DESK / "data" / "universe"
E8_GUARD_SRC = DESK / "prop" / "e8_guard.py"
FUSION_DEADMAN_SRC = DESK / "proposals" / "fusion_deadman.py"
FUSION_STATE = DESK / "data" / "account_state.json"

XAU_OZ_PER_LOT = 100.0
FX_UNITS_PER_LOT = 100_000.0
MIN_LOT = 0.01

#: The one measured E8 gap-through, in points (position_manager.stop_rests_at_venue docstring).
WORST_SLIP_POINTS = 24.13
N_STOP_EXITS_MEASURED = 1
#: The fill price of that exit. Historical replay scales the slip by price, so a 2019 bar at
#: a 1,300 price is charged 24.13 x 1300/4283.91 points, the same fraction of price as the event.
SLIP_REF_PRICE = 4283.91
SLIP_FRAC = WORST_SLIP_POINTS / SLIP_REF_PRICE
SLIP_TAIL_MIN_SAMPLE = 20

#: The live sizes for pass 20 (principal's statement, not read from the box).
E8_RISK_PER_LEG = 0.006
FTMO_RISK_PER_LEG = 0.009

#: FTMO 2-Step public rules (100k nominal). No FTMO module exists in the repo to parse.
FTMO_START = 100_000.0
FTMO_DAILY = 0.05
FTMO_MAX = 0.10

#: SNB 2015-01-15, EURCHF. EXTERNAL: the repo's bars begin in 2018.
SNB_GAP_PCT = {"fill_near_close": 0.144, "fill_at_low": 0.292}

ASIA = next(w for w in GOLD_WINDOWS if w[0] == "asia")
ASIA_SIG_HOUR = int(ASIA[1])
#: gold_asia brackets expire with their session, 6h after the signal (decision_core).
ASIA_ENTRY_END_HOUR = 13


# ------------------------------------------------------------------ rule constants

def parse_constants(path: Path, names: tuple[str, ...]) -> dict[str, float]:
    """Module-level numeric constants by `ast`. The module is never imported, and a missing name
    is simply absent. Pure apart from reading `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            if isinstance(t, ast.Name) and t.id in names:
                try:
                    v = ast.literal_eval(value)  # type: ignore[arg-type]
                except (ValueError, TypeError):
                    continue
                if isinstance(v, (int, float)):
                    out[t.id] = float(v)
    return out


@dataclass(frozen=True)
class Account:
    name: str
    currency: str
    start: float          # equity the stress starts from
    daily_limit: float    # loss in account currency that breaches the daily rule
    max_room: float       # loss in account currency that reaches the max / static floor
    state_basis: str      # MEASURED file, or the assumption made


def e8_account(src: Path = E8_GUARD_SRC) -> Account:
    c = parse_constants(src, ("START_BALANCE", "STATIC_DRAWDOWN", "DAILY_DRAWDOWN"))
    start = c["START_BALANCE"]
    return Account("E8", "USD", start, start * c["DAILY_DRAWDOWN"], start * c["STATIC_DRAWDOWN"],
                   "ASSUMED start balance: E8_GUARD.json / e8_guard_state.json absent, "
                   "current room UNMEASURED")


def ftmo_account() -> Account:
    return Account("FTMO", "USD", FTMO_START, FTMO_START * FTMO_DAILY, FTMO_START * FTMO_MAX,
                   "ASSUMED start balance: no FTMO state file, current room UNMEASURED")


def fusion_account(src: Path = FUSION_DEADMAN_SRC, state: Path = FUSION_STATE) -> Account | None:
    """Fusion is measured or it is None. An unreadable equity is never a default number."""
    c = parse_constants(src, ("EQUITY_FLOOR_EUR", "DAILY_LOSS_PCT"))
    try:
        doc = json.loads(state.read_text(encoding="utf-8"))
        eq = float(doc["equity"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if "EQUITY_FLOOR_EUR" not in c or "DAILY_LOSS_PCT" not in c or not eq > 0:
        return None
    return Account("Fusion", "EUR", eq, eq * c["DAILY_LOSS_PCT"], eq - c["EQUITY_FLOOR_EUR"],
                   f"MEASURED account_state.json updated_at={doc.get('updated_at')}")


def published_account(acct: Account) -> dict[str, Any]:
    """The account as the report publishes it: its limits as fractions of its own starting
    equity. No balance, equity or limit in currency leaves this module."""
    ok = acct.start > 0
    return {"name": acct.name, "currency": acct.currency,
            "daily_limit_frac_of_start": round(acct.daily_limit / acct.start, 5) if ok
            else UNMEASURED,
            "max_room_frac_of_start": round(acct.max_room / acct.start, 5) if ok
            else UNMEASURED,
            "state_basis": acct.state_basis}


# ------------------------------------------------------------------ bars

def load_bars(symbol: str, tf: str = "H1", root: Path = BARS) -> pd.DataFrame:
    df = pd.read_parquet(root / f"{symbol}_{tf}.parquet")
    return df[["open", "high", "low", "close"]].sort_index()


def atr_series(bars: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    """decision_core.atr_last at every bar: the same causal EWM of true range."""
    tr = pd.concat([bars["high"] - bars["low"],
                    (bars["high"] - bars["close"].shift(1)).abs(),
                    (bars["low"] - bars["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n).mean()


# ------------------------------------------------------------------ gold_asia replay

def _stop_fill(open_: float, sl: float, side: int, slip: float) -> float:
    """Fill price of a stop hit inside a bar. If the bar OPENED through the stop it fills at the
    open (gap-through); otherwise at the stop, less `slip` points in the adverse direction."""
    if side == 1:
        return open_ if open_ <= sl else sl - slip
    return open_ if open_ >= sl else sl + slip


def replay_day(day: pd.DataFrame, spec: dict, *, oco: bool = True, slip: float = 0.0,
               close_hour: float = CLOSE_HOUR,
               entry_end_hour: int = ASIA_ENTRY_END_HOUR) -> list[dict[str, float]]:
    """Legs of one gold_asia bracket over one day's bars from the signal hour on. Pure.

    It is conservative where H1 cannot resolve a bar: a stop and a target in the same bar is a
    stop, and with `oco=False` (an OCO cancel that misses, the duplicate-fill case) both legs can
    fill and both can stop out. With `oco=True`, a bar that touches both entries fills only the
    leg nearer the open. Exits are stop, target, or the bar open at the force-close hour.
    """
    legs = {"buy_stop": 1, "sell_stop": -1}
    open_legs: dict[str, dict[str, float]] = {}
    done: list[dict[str, float]] = []
    filled_any = False
    for ts, b in day.iterrows():
        h = ts.hour + ts.minute / 60.0
        o, hi, lo = float(b["open"]), float(b["high"]), float(b["low"])
        if h + 1.0 > close_hour:     # the H1 bar holding the 19:30 close: exit at its open
            for name, p in open_legs.items():
                done.append(_close(p, o, legs[name], "force_close"))
            open_legs.clear()
            break
        new: list[str] = []
        if h < entry_end_hour and not (oco and filled_any):
            for name, side in legs.items():
                if name in open_legs or any(d["leg"] == name for d in done):
                    continue
                px = spec[name]["price"]
                if (side == 1 and hi >= px) or (side == -1 and lo <= px):
                    new.append(name)
            if oco and len(new) == 2:
                new = sorted(new, key=lambda n: abs(spec[n]["price"] - o))[:1]
        for name in new:
            side = legs[name]
            px = spec[name]["price"]
            entry = max(o, px) if side == 1 else min(o, px)
            open_legs[name] = {"entry": entry, "sl": spec[name]["sl"], "tp": spec[name]["tp"],
                               "dist": abs(px - spec[name]["sl"]), "leg": name, "mae": 0.0}
            filled_any = True
        for name in list(open_legs):
            p, side = open_legs[name], legs[name]
            hit_sl = lo <= p["sl"] if side == 1 else hi >= p["sl"]
            hit_tp = hi >= p["tp"] if side == 1 else lo <= p["tp"]
            if not hit_sl:      # a stopped bar's extreme is past the fill; its R is the exit
                worst_px = lo if side == 1 else hi
                p["mae"] = min(p["mae"], (worst_px - p["entry"]) * side / p["dist"])
            if hit_sl:
                done.append(_close(p, _stop_fill(o if name not in new else p["entry"],
                                                 p["sl"], side, slip), side, "stop"))
                del open_legs[name]
            elif hit_tp:
                done.append(_close(p, p["tp"], side, "target"))
                del open_legs[name]
    else:
        last = float(day["close"].iloc[-1]) if len(day) else 0.0
        for name, p in open_legs.items():
            done.append(_close(p, last, legs[name], "end_of_data"))
    return done


def _close(p: dict[str, Any], px: float, side: int, why: str) -> dict[str, Any]:
    """A closed leg. `mae_r` is the worst R it showed while open (bar extremes), never better
    than where it closed: what a floating-inclusive daily rule sees."""
    r = (px - p["entry"]) * side / p["dist"]
    return {"leg": p["leg"], "entry": p["entry"], "exit": px, "dist": p["dist"],
            "r": r, "mae_r": min(float(p.get("mae", 0.0)), r), "why": why}


def replay_gold_asia(bars: pd.DataFrame, *, oco: bool = True, slip_frac: float = 0.0
                     ) -> pd.DataFrame:
    """One row per day the gold_asia bracket formed: the day's summed R, leg count and stop
    distance. The bracket is built by decision_core.bracket_spec from the range of hours
    [0, 7) and the ATR of the bars before the signal (floor 5.0, tick 0.01, stops_level 0),
    exactly as e8_gold.plan sends it. Every stop exit is charged `slip_frac` x the signal-hour
    price in adverse points; a stop the bar opened through fills at the open instead."""
    atr = atr_series(bars)
    rows = []
    for date, day in bars.groupby(bars.index.date):
        pre = day[day.index.hour < ASIA_SIG_HOUR]
        post = day[day.index.hour >= ASIA_SIG_HOUR]
        if pre.empty or post.empty:
            continue
        a = atr.loc[:pre.index[-1]].iloc[-1]
        if not (a == a and a > 0):          # NaN before ATR_N bars exist
            continue
        spec = bracket_spec(float(pre["high"].max()), float(pre["low"].min()),
                            max(float(a), 5.0), 0.01, stops_level=0)
        px = float(pre["close"].iloc[-1])
        legs = replay_day(post, spec, oco=oco, slip=slip_frac * px)
        dist = abs(spec["buy_stop"]["price"] - spec["buy_stop"]["sl"])
        rows.append({"date": pd.Timestamp(date), "r": float(sum(x["r"] for x in legs)),
                     "worst_intraday_r": float(sum(x["mae_r"] for x in legs)),
                     "n_legs": len(legs), "n_stops": sum(x["why"] == "stop" for x in legs),
                     "worst_leg_r": min((x["r"] for x in legs), default=0.0), "dist": dist,
                     "price": px})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(
        columns=["r", "worst_intraday_r", "n_legs", "n_stops", "worst_leg_r", "dist", "price"])


# ------------------------------------------------------------------ scenario magnitudes

def flash_crash_atr_mult(bars: pd.DataFrame) -> dict[str, Any]:
    """The largest one-bar adverse excursion, open to extreme, in multiples of the previous
    bar's ATR, either direction."""
    atr = atr_series(bars).shift(1)
    down = (bars["open"] - bars["low"]) / atr
    up = (bars["high"] - bars["open"]) / atr
    exc = pd.concat([down, up], axis=1).max(axis=1).dropna()
    ts = exc.idxmax()
    return {"atr_mult": float(exc.max()), "at": ts.isoformat(),
            "p999_atr_mult": float(exc.quantile(0.999)), "n_bars": int(exc.size)}


def weekend_gap_pct(bars: pd.DataFrame) -> dict[str, Any]:
    """Largest |first open after a >=36h break / last close before it - 1|."""
    idx = bars.index
    gaps = idx.to_series().diff() >= pd.Timedelta(hours=36)
    after = np.flatnonzero(gaps.to_numpy())
    vals = []
    for i in after:
        prev_close = float(bars["close"].iloc[i - 1])
        vals.append((abs(float(bars["open"].iloc[i]) / prev_close - 1.0), idx[i]))
    if not vals:
        return {"pct": UNMEASURED, "n_weekends": 0}
    pcts = np.array([v[0] for v in vals])
    worst = max(vals, key=lambda v: v[0])
    return {"pct": float(worst[0]), "at": worst[1].isoformat(),
            "p99_pct": float(np.quantile(pcts, 0.99)), "n_weekends": len(vals)}


# ------------------------------------------------------------------ the stress arithmetic

def leg_loss(adverse_points: float, stop_dist: float, risk_ccy: float) -> float:
    """Loss on one leg sized so a clean stop costs `risk_ccy`, when the fill is `adverse_points`
    from entry. A gap smaller than the stop is still a stop at the stop (plus slip, which the
    caller adds into adverse_points)."""
    return risk_ccy * max(adverse_points, 0.0) / stop_dist


def verdict(loss: float, acct: Account) -> dict[str, Any]:
    v = ("BREACH_MAX" if loss >= acct.max_room else
         "BREACH_DAILY" if loss >= acct.daily_limit else "SURVIVES_FULL_ROOM")
    # NO MONEY FIGURE IS PUBLISHED: the loss is a fraction of the account's own starting equity,
    # beside its share of each limit. The account-currency amount stays in memory only.
    return {"loss_frac_of_start": round(loss / acct.start, 5) if acct.start > 0 else UNMEASURED,
            "pct_of_daily_limit": round(100 * loss / acct.daily_limit, 1),
            "pct_of_max_room": round(100 * loss / acct.max_room, 1),
            "verdict_vs_full_room": v,
            "verdict_vs_current_room": (v if acct.state_basis.startswith("MEASURED")
                                        else UNMEASURED)}


def stress(*, xau: pd.DataFrame, audchf: pd.DataFrame, eurchf: pd.DataFrame,
           eurusd: pd.DataFrame, accounts: dict[str, Account | None], legs: int = 2,
           e8_risk: float = E8_RISK_PER_LEG, ftmo_risk: float = FTMO_RISK_PER_LEG,
           recent_days: int = 60) -> dict[str, Any]:
    """Per scenario, per account: loss, share of each limit, and verdict. Pure on its inputs."""
    rep = replay_gold_asia(xau, oco=False, slip_frac=SLIP_FRAC)
    recent = rep.tail(recent_days)
    stop_dist = float(recent["dist"].median())
    stop_dist_p10 = float(recent["dist"].quantile(0.10))
    price = float(xau["close"].iloc[-1])
    atr_now = float(atr_series(xau).iloc[-1])
    eurusd_px = float(eurusd["close"].iloc[-1])
    audchf_px = float(audchf["close"].iloc[-1])
    eurchf_px = float(eurchf["close"].iloc[-1])
    flash = flash_crash_atr_mult(xau)
    wknd = weekend_gap_pct(xau)

    # adverse points at the fill, per gold leg, slip included where the fill is a stop
    gold_moves: dict[str, float] = {
        f"snb_2015_{k}": price * g for k, g in SNB_GAP_PCT.items()}
    gold_moves["flash_crash"] = max(flash["atr_mult"] * atr_now, stop_dist) + WORST_SLIP_POINTS
    gold_moves["weekend_gap"] = (max(price * wknd["pct"], stop_dist) + WORST_SLIP_POINTS
                                 if isinstance(wknd["pct"], float) else float("nan"))

    def risk_ccy(name: str, acct: Account) -> float:
        if name == "E8":
            return acct.start * e8_risk
        if name == "FTMO":
            return acct.start * ftmo_risk
        return MIN_LOT * XAU_OZ_PER_LOT * stop_dist / eurusd_px   # Fusion min lot, in EUR

    out: dict[str, Any] = {}
    for scen, pts in gold_moves.items():
        out[scen] = {"adverse_points_per_leg": round(pts, 2), "legs": legs, "accounts": {}}
        for name, acct in accounts.items():
            if acct is None:
                out[scen]["accounts"][name] = UNMEASURED
                continue
            loss = legs * leg_loss(pts, stop_dist, risk_ccy(name, acct))
            if name == "Fusion" and scen.startswith("snb_2015"):
                g = SNB_GAP_PCT[scen.removeprefix("snb_2015_")]
                chf = MIN_LOT * FX_UNITS_PER_LOT * audchf_px * g
                loss += chf / eurchf_px
            out[scen]["accounts"][name] = verdict(loss, acct)
    # worst replay day, both OCO variants, slip tail on every stop: its R on each account
    variants = {"replay_worst_day_oco_fail": rep,
                "replay_worst_day_oco": replay_gold_asia(xau, oco=True, slip_frac=SLIP_FRAC)}
    for key, rv in variants.items():
        wd = rv["r"].idxmin()
        wr = float(rv.loc[wd, "r"])
        out[key] = {"date": str(wd.date()), "day_r": round(wr, 3),
                    "n_legs": int(rv.loc[wd, "n_legs"]), "accounts": {}}
        for name, acct in accounts.items():
            out[key]["accounts"][name] = (
                UNMEASURED if acct is None else verdict(-wr * risk_ccy(name, acct), acct))

    breakeven: dict[str, Any] = {}
    for name, acct in accounts.items():
        if acct is None:
            breakeven[name] = UNMEASURED
            continue
        per_pt = legs * risk_ccy(name, acct) / stop_dist
        breakeven[name] = {"adverse_points_per_leg_to_daily": round(acct.daily_limit / per_pt, 2),
                           "adverse_points_per_leg_to_max": round(acct.max_room / per_pt, 2),
                           "as_pct_of_price_to_daily": round(
                               100 * acct.daily_limit / per_pt / price, 3)}
    return {
        "inputs": {"gold_price": price, "atr_h1_now": round(atr_now, 3),
                   "stop_dist_median_recent": round(stop_dist, 3),
                   "stop_dist_p10_recent": round(stop_dist_p10, 3),
                   "recent_days": recent_days, "eurusd": eurusd_px, "audchf": audchf_px,
                   "eurchf": eurchf_px, "legs": legs, "e8_risk_per_leg": e8_risk,
                   "ftmo_risk_per_leg": ftmo_risk, "fusion_lot": MIN_LOT,
                   "slip_points": WORST_SLIP_POINTS,
                   "slip_basis": (f"{N_STOP_EXITS_MEASURED} measured E8 stop exit; placeholder "
                                  f"until {SLIP_TAIL_MIN_SAMPLE}+ (books.sim_v3 absent)"),
                   "flash_crash": flash, "weekend_gap": wknd,
                   "snb_gap_pct": SNB_GAP_PCT, "snb_basis": "EXTERNAL (repo bars start 2018)",
                   "xau_bars": [xau.index[0].isoformat(), xau.index[-1].isoformat()]},
        "accounts": {k: (UNMEASURED if v is None else published_account(v))
                     for k, v in accounts.items()},
        "scenarios": out,
        "breakeven": breakeven,
        "replay_summary": {k: {"days": len(v), "worst_day_r": round(float(v["r"].min()), 3),
                               "p01_day_r": round(float(v["r"].quantile(0.01)), 3),
                               "mean_day_r": round(float(v["r"].mean()), 4)}
                           for k, v in variants.items()},
    }


def build(legs: int = 2) -> dict[str, Any]:
    accounts: dict[str, Account | None] = {"E8": e8_account(), "FTMO": ftmo_account(),
                                           "Fusion": fusion_account()}
    body = stress(xau=load_bars("XAUUSD"), audchf=load_bars("AUDCHF"),
                  eurchf=load_bars("EURCHF"), eurusd=load_bars("EURUSD"),
                  accounts=accounts, legs=legs)
    return {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "idea_queue_row": 13, "report_only": True, **body}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--legs", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build(a.legs)
    text = json.dumps(doc, indent=1, default=str)
    if a.dry_run:
        print(text)
    else:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
        print(a.out)
    return 0

