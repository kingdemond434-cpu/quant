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
import time
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

BASE = Path(r"C:\Users\dell\mt5-research")
STATE = BASE / "data" / "gateway_state.json"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "gateway.log"

TERMINAL = r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"
MAGIC = 341953

LOT = 0.02              # gold book lot; mandate-optimal q=5.5% (sizing study 2026-08-16)
Q_OPT = 0.055           # risk fraction of equity per trade (robust geometric optimum)
DIST_USD = 19.1         # ~1.2xATR stop distance (USD/oz), used for auto lot scaling
CONTRACT_OZ = 100
FX_EUR = 0.92
RR = 2.0
ATR_N = 20
CANCEL_HOUR = 20.5      # cancel unfilled brackets at 20:30 UTC
CLOSE_HOUR = 19.5       # force-close positions at 19:30 UTC
PROMOTED_LOT = 0.01     # promoted sleeves stay at minimum lot until months of proof

# (label, signal_hour, range window)  range None => [0, signal_hour)
GOLD_WINDOWS = [
    ("asia", 7, None),
    ("london_am", 13, (10, 13)),
    ("ny_open", 14, (13, 14)),
    ("afternoon", 17, (14, 17)),
]


def auto_lot(equity: float) -> float:
    """Fixed-fractional sizing: q_opt of equity per trade, rounded to 0.01."""
    lot = Q_OPT * equity / (DIST_USD * CONTRACT_OZ * FX_EUR)
    lot = round(lot / 0.01) * 0.01
    return float(min(max(lot, 0.01), 5.0))


def load_sleeves() -> list[dict]:
    """Promoted sleeves from data/sleeves.json (writer: research/promoter.py)."""
    if not SLEEVES_FILE.exists():
        return []
    try:
        data = json.loads(SLEEVES_FILE.read_text(encoding="utf-8"))
        return [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
    except Exception:
        return []


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
               "commission": d.commission, "swap": d.swap, "deal": d.ticket}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        written += 1
    if written:
        log(f"ledger: recorded {written} closed trade(s)")


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
                        "lot": PROMOTED_LOT, "status": "LIVE"})
    return sleeves


def main() -> None:
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
            lot = auto_lot(equity) if s["lot"] == "auto" else float(s["lot"])
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