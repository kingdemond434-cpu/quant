"""LIVE DEMO portfolio executor -- the Python brain trades the target portfolio on MT5 (demo only).

Reads the brain's target weights (data/target_portfolio.json, refreshed by run_crossasset_shadow),
sizes ALL of them to meaningful lots at a target gross leverage, scales the book to fit broker
margin (so nothing rounds to zero and nothing gets rejected), diffs against current positions, and
sends the deltas as market orders. Writes web/live.json for the dashboard. Loops every --interval.

SIZING: gross notional = equity x --gross-leverage, split by weight, floored at each symbol's
minimum lot so every instrument trades; then scaled down if total margin would exceed --margin-frac
of free margin. Bigger lots come from raising --gross-leverage (margin is the real limit).

SAFETY (non-negotiable):
  * refuses to run on anything but a DEMO account (trade_mode == 0);
  * never uses more than --margin-frac of free margin (default 0.5);
  * only manages its own positions (by magic number);
  * --dry-run is the DEFAULT; pass --live to actually send orders.

    python scripts/run_portfolio_live.py --live --gross-leverage 5 --minutes 120 --interval 120
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

_TARGET = Path("data/target_portfolio.json")
_WEB = Path("web/live.json")
_MAGIC = 770001
_MIN_REBAL_LOTS = 1e-9


def _filling(mt5, symbol: str):  # type: ignore[no-untyped-def]
    info = mt5.symbol_info(symbol)
    mode = getattr(info, "filling_mode", 0)
    if mode & 2:
        return mt5.ORDER_FILLING_IOC
    if mode & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _target_lots(mt5, weights: dict[str, float],  # type: ignore[no-untyped-def]
                 gross_notional: float) -> dict[str, float]:
    """Size every weight to a lot, floored at the broker minimum so all instruments trade."""
    out: dict[str, float] = {}
    for sym, w in weights.items():
        if w == 0.0 or not mt5.symbol_select(sym, True):
            continue
        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if info is None or tick is None or not (tick.bid or tick.ask):
            continue
        price = float(tick.ask if w > 0 else tick.bid) or float(tick.bid or tick.ask)
        contract = float(info.trade_contract_size) or 1.0
        step = float(info.volume_step) or 0.01
        raw = abs(gross_notional * w) / (contract * price)
        lots = round(raw / step) * step
        lots = min(max(lots, float(info.volume_min)), float(info.volume_max))
        out[sym] = lots if w > 0 else -lots
    return out


def _margin(mt5, sym: str, lots: float) -> float:  # type: ignore[no-untyped-def]
    tick = mt5.symbol_info_tick(sym)
    if tick is None:
        return 0.0
    side = mt5.ORDER_TYPE_BUY if lots > 0 else mt5.ORDER_TYPE_SELL
    price = float(tick.ask if lots > 0 else tick.bid) or float(tick.bid or tick.ask)
    m = mt5.order_calc_margin(side, sym, abs(lots), price)
    return float(m) if m else 0.0


def _notional(mt5, sym: str, lots: float) -> float:  # type: ignore[no-untyped-def]
    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None:
        return 0.0
    return abs(lots) * float(info.trade_contract_size) * float(tick.bid or tick.ask)


def _current_lots(mt5) -> dict[str, float]:  # type: ignore[no-untyped-def]
    cur: dict[str, float] = {}
    for p in mt5.positions_get() or []:
        if p.magic != _MAGIC:
            continue
        q = p.volume if p.type == mt5.POSITION_TYPE_BUY else -p.volume
        cur[p.symbol] = cur.get(p.symbol, 0.0) + q
    return cur


def _round_to_step(mt5, sym: str, lots: float) -> float:  # type: ignore[no-untyped-def]
    info = mt5.symbol_info(sym)
    step = float(info.volume_step) or 0.01
    out = round(abs(lots) / step) * step
    out = min(max(out, float(info.volume_min)), float(info.volume_max)) if out > 0 else 0.0
    return out if lots >= 0 else -out


def _send(mt5, symbol: str, delta: float, *, dry: bool) -> dict[str, object]:  # type: ignore
    side = "buy" if delta > 0 else "sell"
    tick = mt5.symbol_info_tick(symbol)
    price = float(tick.ask if delta > 0 else tick.bid)
    if dry:
        return {"symbol": symbol, "side": side, "lots": round(abs(delta), 3), "status": "DRY"}
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": round(abs(delta), 3),
        "type": mt5.ORDER_TYPE_BUY if delta > 0 else mt5.ORDER_TYPE_SELL, "price": price,
        "deviation": 50, "magic": _MAGIC, "comment": "quant_portfolio",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": _filling(mt5, symbol),
    }
    res = mt5.order_send(req)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    return {"symbol": symbol, "side": side, "lots": round(abs(delta), 3),
            "status": "FILLED" if ok else f"REJ {getattr(res, 'retcode', '?')}",
            "comment": getattr(res, "comment", "")}


def _rebalance(mt5, weights: dict[str, float], gross_leverage: float,  # type: ignore
               margin_frac: float, *, dry: bool) -> dict[str, object]:
    acct = mt5.account_info()
    equity = float(acct.equity)
    free = float(acct.margin_free)
    target = {s: v for s, v in _target_lots(mt5, weights, equity * gross_leverage).items()
              if v != 0.0}
    # Margin-aware scale-down: keep total required margin within margin_frac of free margin.
    total_margin = sum(_margin(mt5, s, v) for s, v in target.items())
    budget = free * margin_frac
    if total_margin > budget and total_margin > 0:
        scale = budget / total_margin
        target = {s: lv for s, v in target.items()
                  if (lv := _round_to_step(mt5, s, v * scale)) != 0.0}
        total_margin = sum(_margin(mt5, s, v) for s, v in target.items())
    current = _current_lots(mt5)
    orders = []
    for sym in sorted(set(target) | set(current)):
        info = mt5.symbol_info(sym)
        vmin = float(info.volume_min) if info else 0.01
        delta = target.get(sym, 0.0) - current.get(sym, 0.0)
        if abs(delta) >= max(vmin, _MIN_REBAL_LOTS):
            orders.append(_send(mt5, sym, delta, dry=dry))
    gross_notional = sum(_notional(mt5, s, v) for s, v in target.items())
    return {"equity": round(equity, 2), "free_margin": round(free, 2),
            "margin_used_est": round(total_margin, 2), "n_target": len(target),
            "gross_notional": round(gross_notional, 2),
            "gross_leverage": round(gross_notional / equity, 2) if equity else 0.0,
            "orders": orders}


def main() -> None:
    import MetaTrader5 as mt5

    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--gross-leverage", type=float, default=5.0,
                    help="target gross notional as a multiple of equity (margin is the real limit)")
    ap.add_argument("--margin-frac", type=float, default=0.5,
                    help="never use more than this fraction of free margin")
    ap.add_argument("--live", action="store_true", help="actually send orders (default = dry-run)")
    args = ap.parse_args()
    dry = not args.live
    gl = max(0.0, args.gross_leverage)
    mf = min(max(args.margin_frac, 0.0), 0.9)

    if not _TARGET.exists():
        raise SystemExit(f"no target portfolio at {_TARGET}; run scripts/run_crossasset_shadow.py")
    weights = {k: float(v) for k, v in json.loads(_TARGET.read_text("utf-8"))["weights"].items()}

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mode = getattr(acct, "trade_mode", "?")
        mt5.shutdown()
        raise SystemExit(f"refusing to trade: account trade_mode={mode} is not DEMO")
    print(f"connected DEMO login={acct.login} server={acct.server} equity={acct.equity:.2f} "
          f"free_margin={acct.margin_free:.2f}")
    print(f"target gross-leverage={gl}x  margin-frac={mf}  {'DRY-RUN' if dry else 'LIVE'}  "
          f"{len(weights)} instruments")

    deadline = time.monotonic() + args.minutes * 60.0
    try:
        while time.monotonic() < deadline:
            last = _rebalance(mt5, weights, gl, mf, dry=dry)
            ok = [o for o in last["orders"] if str(o["status"]).startswith(("FILLED", "DRY"))]
            rej = [o for o in last["orders"] if str(o["status"]).startswith("REJ")]
            print(f"[{datetime.now(UTC):%H:%M:%S}] equity={last['equity']} "
                  f"gross=${last['gross_notional']} ({last['gross_leverage']}x) "
                  f"margin_used~${last['margin_used_est']} positions={last['n_target']} "
                  f"orders={len(last['orders'])} ok={len(ok)} rej={len(rej)}")
            _WEB.parent.mkdir(parents=True, exist_ok=True)
            _WEB.write_text(json.dumps({
                "updated": datetime.now(tz=UTC).isoformat(), "mode": "dry" if dry else "live",
                "account": {"login": acct.login, "server": acct.server,
                            "balance": acct.balance, "equity": last["equity"]},
                **last}, indent=2, default=str), "utf-8")
            time.sleep(args.interval)
    finally:
        mt5.shutdown()
    print("live session done.")


if __name__ == "__main__":
    main()
