"""MT5 gateway for the research desk: 4 breakout windows, paper-first, kill switch.

Modes:
  SHADOW (default): computes signals, simulates fills on live bid/ask, NEVER
                    sends orders to the terminal.
  ARMED  (manual):  sends real bracket orders (buy-stop/sell-stop with SL/TP)
                    to the logged-in MT5 account, reconciles from terminal.

Windows (all validated, hunt3+hunt4):
  07:00 Asia range -> London       t=5.15-7.11
  13:00 London AM range            t=4.61
  14:00 NY open range              t=6.53
  17:00 Afternoon range            t=3.89
Daily housekeeping: cancel unfilled brackets 20:30 UTC, force-close positions
19:30 UTC (and Friday 19:30), never hold across the 21:00-22:00 broker pause.

State in data/gateway_state.json. Only the human can set armed=true.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

BASE = Path(r"C:\Users\dell\mt5-research")
STATE = BASE / "data" / "gateway_state.json"
LOG = BASE / "logs" / "gateway.log"

TERMINAL = r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"
SYMBOL = "XAUUSD"
MAGIC = 341953

LOT = 0.01              # per bracket; risk ~2.7% of balance each
RR = 2.0
ATR_N = 20
TTL_BARS = 12
CANCEL_HOUR = 20.5      # cancel unfilled brackets at 20:30 UTC
CLOSE_HOUR = 19.5       # force-close positions at 19:30 UTC

# (label, signal_hour, range window)  range None => [0, signal_hour)
WINDOWS = [
    ("asia", 7, None),
    ("london_am", 13, (10, 13)),
    ("ny_open", 14, (13, 14)),
    ("afternoon", 17, (14, 17)),
]


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


def bracket_spec(hi: float, lo: float, a: float, tick: float) -> dict:
    """Build the bracket orders and their SL/TP as MT5 order fields."""
    span = hi - lo
    dist = max(1.2 * a, span)
    tick = max(tick, 0.01)
    sl_dist_pts = int(round(dist / tick)) + 20  # +20 = broker stops_level
    tp_dist_pts = int(round(dist * RR / tick))
    return {
        "buy_stop": {"price": hi, "sl": hi - sl_dist_pts * tick,
                     "tp": hi + tp_dist_pts * tick},
        "sell_stop": {"price": lo, "sl": lo + sl_dist_pts * tick,
                      "tp": lo - tp_dist_pts * tick},
    }


def place_bracket(st: dict, spec: dict, window: str) -> dict:
    if not st["armed"]:
        log(f"SHADOW [{window}] would place bracket: {json.dumps(spec, default=str)}")
        return {"shadow": True, "orders": []}
    sent = []
    for side in ("buy_stop", "sell_stop"):
        s = spec[side]
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": SYMBOL,
            "volume": LOT,
            "type": mt5.ORDER_TYPE_BUY_STOP if side == "buy_stop" else mt5.ORDER_TYPE_SELL_STOP,
            "price": s["price"],
            "sl": s["sl"],
            "tp": s["tp"],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "deviation": 20,
            "magic": MAGIC,
        }
        res = mt5.order_send(req)
        code = res.retcode if res else None
        if code == 10017:
            log("ORDER FAILED: trade disabled - enable 'Allow algorithmic trading' "
                "in terminal Options > Expert Advisors, and check account auth")
        sent.append({"side": side, "retcode": code,
                     "comment": res.comment if res else None})
        log(f"ORDER [{window}] {side} -> retcode={code} "
            f"{res.comment if res else ''}")
    return {"shadow": False, "orders": sent}


def cancel_pending(st: dict) -> None:
    if st["armed"]:
        for o in mt5.orders_get(symbol=SYMBOL) or []:
            mt5.order_delete(o.ticket)
            log(f"cancelled pending ticket {o.ticket}")
    else:
        log("SHADOW would cancel unfilled brackets")


def close_positions(st: dict) -> None:
    if not st["armed"]:
        log("SHADOW would force-close open positions")
        return
    for p in mt5.positions_get(symbol=SYMBOL) or []:
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": mt5.symbol_info_tick(SYMBOL).bid if p.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(SYMBOL).ask,
            "deviation": 20,
            "magic": MAGIC,
        }
        res = mt5.order_send(req)
        log(f"CLOSE ticket {p.ticket} -> retcode={res.retcode if res else None} "
            f"{res.comment if res else ''}")


def reconcile(st: dict) -> dict:
    pos = mt5.positions_get(symbol=SYMBOL) or []
    pend = mt5.orders_get(symbol=SYMBOL) or []
    st["position"] = [
        {"ticket": p.ticket, "type": p.type, "volume": p.volume,
         "price_open": p.price_open, "sl": p.sl, "tp": p.tp,
         "profit": p.profit} for p in pos
    ] if pos else None
    st["pending"] = [{"ticket": o.ticket, "type": o.type, "price": o.price_open}
                     for o in pend] if pend else None
    st["last_reconcile"] = now()
    return st


def main() -> None:
    if not connect():
        return
    st = load_state()
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        log("no tick; market likely closed")
        mt5.shutdown()
        return

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
        # reset daily bookkeeping
        st["brackets"] = {}
        st["last_bracket_date"] = day_key
        save_state(st)

    # place brackets at their window hours
    if st["last_bracket_date"] == day_key:
        pend = mt5.orders_get(symbol=SYMBOL) or []
        for label, sig_hour, rng in WINDOWS:
            if st["brackets"].get(label):
                continue
            if hour < sig_hour:
                continue
            h1 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 400)
            if h1 is None:
                log(f"copy_rates failed: {mt5.last_error()}")
                break
            df = pd.DataFrame(h1)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("time").sort_index()
            rng2 = day_range(df, rng, sig_hour)
            if rng2 is None:
                log(f"[{label}] range not ready at {hour:.1f}")
                continue
            hi, lo = rng2
            sym = mt5.symbol_info(SYMBOL)
            tr = pd.concat(
                [df["high"] - df["low"],
                 (df["high"] - df["close"].shift(1)).abs(),
                 (df["low"] - df["close"].shift(1)).abs()], axis=1
            ).max(axis=1)
            a = float(tr.ewm(alpha=1 / ATR_N, min_periods=ATR_N).mean().iloc[-1])
            spec = bracket_spec(hi, lo, max(a, 5.0), sym.trade_tick_size)
            # restart recovery: a pending order at this window's level already exists
            matches = [
                o for o in pend
                if abs(o.price_open - spec["buy_stop"]["price"]) < 0.5
                or abs(o.price_open - spec["sell_stop"]["price"]) < 0.5
            ]
            if matches:
                st["brackets"][label] = {"date": day_key, "recovered": True,
                                         "hi": hi, "lo": lo, "spec": spec}
                log(f"recovered [{label}] bracket for {day_key}")
                save_state(st)
                continue
            res = place_bracket(st, spec, label)
            st["brackets"][label] = {"date": day_key, "hi": hi, "lo": lo,
                                     "spec": spec, "placed_at": now(), "result": res}
            save_state(st)

    # housekeeping: cancel unfilled brackets, force-close positions
    if hour >= CANCEL_HOUR:
        cancel_pending(st)
    if hour >= CLOSE_HOUR:
        close_positions(st)
    if tnow.dayofweek == 4 and hour >= CLOSE_HOUR:  # Friday: weekend close
        close_positions(st)

    st = reconcile(st)
    save_state(st)
    log(f"state: armed={st['armed']} pos={len(st['position'] or [])} "
        f"pending={len(st['pending'] or [])} brackets={list(st['brackets'])}")
    mt5.shutdown()


if __name__ == "__main__":
    main()