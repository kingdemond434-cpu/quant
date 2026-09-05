"""Binance Futures TESTNET executor -- the Python brain trades the crypto target on testnet only.

Reads data/crypto_target.json (brain), sizes to qty at a gross-leverage cap, diffs vs current
testnet positions, and places market orders. Records every fill to a trade DB; snapshots account +
positions to web/crypto_testnet.json for the dashboard. Connector is pinned to the TESTNET (cannot
touch a live account); keys come from the environment, never code.

SAFETY: dry-run is DEFAULT (pass --live to send); kill-switch file data/CRYPTO_KILL flattens+halts;
daily-loss stop; gross-leverage cap; max positions. No alpha logic here -- it only executes weights.

    set BINANCE_TESTNET_KEY=... & set BINANCE_TESTNET_SECRET=...
    python scripts/run_crypto_testnet.py --live --gross-leverage 2 --minutes 120 --interval 300
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.execution import binance_testnet as bt
from libs.execution.maker import maker_execute_batch, maker_share

_TARGET = Path("data/crypto_target.json")
_WEB = Path("web/crypto_testnet.json")
_DB = Path("data/crypto_trades.sqlite")
_STATE = Path("data/crypto_testnet_state.json")
_KILL = Path("data/CRYPTO_KILL")
_HB = Path("data/executor_heartbeat")          # single-instance lock (prevents double-trading)
_REGIME = Path("data/crypto_regime.json")
_LEVTARGET = Path("data/leverage_target.json")      # edge-gated base leverage (forward-validated)
_LAST_ARCHIVE = Path("data/.last_metrics_archive")  # 1x/day data-flywheel marker


def _another_live_executor() -> bool:
    """True if another live executor wrote a heartbeat in the last 120s."""
    if not _HB.exists():
        return False
    try:
        return (time.time() - _HB.stat().st_mtime) < 120.0
    except OSError:
        return False


def _daily_data_tasks() -> None:
    """Keep the DATA FLYWHEEL turning off the always-on loop instead of the fragile nightly task.

    Once per UTC day, archive OI/long-short/taker (this grows the 40-day clock that gates the whole
    OI / liquidation / long-short alpha column) and refresh the live regime tag. Process-isolated
    via subprocess so any data hiccup can never crash the executor. The nightly scheduled task kept
    failing (exit 1), freezing the archive at a single snapshot -- this makes accumulation as robust
    as the trader itself, which has to be alive anyway."""
    today = datetime.now(tz=UTC).date().isoformat()
    if _LAST_ARCHIVE.exists() and _LAST_ARCHIVE.read_text("utf-8").strip() == today:
        return
    root = Path(__file__).resolve().parent.parent
    # quick collectors (blocking, ~mins) -- the data flywheel that gates the derivative alpha column
    for script in ("scripts/collect_binance_metrics.py", "scripts/collect_market_breadth.py",
                   "scripts/collect_deribit_surface.py", "scripts/classify_regime.py",
                   "scripts/run_regime_engine.py"):
        try:
            subprocess.run([sys.executable, script], cwd=root, timeout=600,
                           capture_output=True, text=True, check=False)
        except Exception as e:  # never let a data task abort a trading cycle
            print(f"[daily-task] {script}: {e!r}"[:140])
    # heavy research chain (detached, non-blocking) -- replaces the fragile QuantDaily task
    try:
        subprocess.Popen([sys.executable, "scripts/run_daily_research.py"], cwd=root,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[daily-task] run_daily_research spawn: {e!r}"[:140])
    _LAST_ARCHIVE.write_text(today, "utf-8")


def _read_regime() -> str:
    try:
        return str(json.loads(_REGIME.read_text("utf-8")).get("regime", "—"))
    except Exception:
        return "—"


def _read_gated_leverage(cap: float) -> float:
    """Edge-gated BASE leverage (small until the forward shadow validates an edge), never above the
    operator cap. Defaults to the cap if the gating file is absent (e.g. before the first run)."""
    try:
        v = float(json.loads(_LEVTARGET.read_text("utf-8")).get("gated_leverage", cap))
        return max(0.5, min(cap, v))
    except Exception:
        return cap


def _read_regime_mult() -> float:
    """Regime leverage multiplier from the HMM engine (de-risk only). Clamped [0.2, 1.0]; 1.0 if
    absent so the executor never levers UP on a regime read -- it only cuts in risky regimes."""
    try:
        m = float(json.loads(_REGIME.read_text("utf-8")).get("leverage_multiplier", 1.0))
        return max(0.2, min(1.0, m))
    except Exception:
        return 1.0


def _lev_tier(throttle: float) -> str:
    """Human label for the drawdown-throttle leverage stage shown on the desk."""
    return {
        1.0: "FULL", 0.7: "-30% (DD>5%)", 0.4: "-60% (DD>10%)", 0.2: "-80% (DD>20%)",
    }.get(throttle, f"x{throttle}")


def _curve_sharpe(curve: list[tuple[str, float]]) -> float | None:
    """Annualized Sharpe of the realized equity curve, daily-resampled. Noisy on a few days (the
    dashboard labels it as such); None until there are >=3 distinct UTC days."""
    by_day: dict[str, float] = {}
    for t, e in curve:
        by_day[t[:10]] = float(e)           # last equity recorded each UTC day
    eqs = [by_day[d] for d in sorted(by_day)]
    if len(eqs) < 3:
        return None
    rets = [eqs[i] / eqs[i - 1] - 1.0 for i in range(1, len(eqs)) if eqs[i - 1]]
    if len(rets) < 2:
        return None
    sd = statistics.pstdev(rets)
    if sd == 0:
        return None
    return round((statistics.fmean(rets) / sd) * (365 ** 0.5), 2)


def _db() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_DB)
    con.execute("CREATE TABLE IF NOT EXISTS trades(ts TEXT, symbol TEXT, side TEXT, qty REAL, "
                "status TEXT, detail TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS account(ts TEXT, balance REAL, n_positions INT, "
                "gross_notional REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS equity_curve(ts TEXT, equity REAL, unrealized REAL, "
                "realized REAL, funding REAL)")
    con.commit()
    return con


_WEBPERF = Path("web/binance.json")


def _performance(con: sqlite3.Connection, pnl: dict[str, float],  # type: ignore[no-untyped-def]
                 snap: dict[str, object], mode: str,
                 extra: dict[str, object] | None = None) -> None:
    """Record equity + write the Binance front-page performance feed (web/binance.json).

    Everything PnL is reported SINCE THE DRAWDOWN-LOCK FIX -- i.e. since the first equity row this
    DB recorded (post-fix equity tracking began then). The pre-fix churn flatten (legacy ~-$1k) is
    deliberately excluded from win-rate / gross / net so the desk shows THIS regime's behaviour, not
    a one-off accident. Account-lifetime realized is still surfaced separately for full honesty."""
    ts = datetime.now(tz=UTC).isoformat()
    con.execute("INSERT INTO equity_curve VALUES(?,?,?,?,?)",
                (ts, pnl["equity"], pnl["unrealized_pnl"], pnl["realized_pnl"],
                 pnl["funding_earned"]))
    con.commit()
    curve = con.execute("SELECT ts,equity FROM equity_curve ORDER BY ts").fetchall()
    fix_ts = curve[0][0] if curve else ts                 # since-fix boundary = first recorded row
    fix_eq = float(curve[0][1]) if curve else float(pnl["equity"])
    try:
        fix_ms = int(datetime.fromisoformat(fix_ts).timestamp() * 1000)
    except ValueError:
        fix_ms = 0

    wins = losses = 0
    gross_profit = gross_loss = realized_fix = funding_fix = 0.0
    if bt.has_keys():
        try:
            rt = bt.realized_trades(fix_ms)
            wins = sum(1 for x in rt if x > 0)
            losses = sum(1 for x in rt if x < 0)
            gross_profit = round(sum(x for x in rt if x > 0), 2)
            gross_loss = round(sum(x for x in rt if x < 0), 2)
            inc = bt.income_summary(fix_ms)
            realized_fix = round(inc["realized_pnl"], 2)
            funding_fix = round(inc["funding"], 2)
        except Exception:
            pass
    win_rate = round(wins / (wins + losses), 3) if (wins + losses) else 0.0
    net_fix = round(gross_profit + gross_loss, 2)

    eqs = [float(e) for _, e in curve]
    peak = max(eqs) if eqs else float(pnl["equity"])
    cur_eq = float(pnl["equity"])
    since_ret = round((cur_eq / fix_eq - 1.0) * 100, 2) if fix_eq else 0.0
    since_peak = round((peak / fix_eq - 1.0) * 100, 2) if fix_eq else 0.0
    dd_pct = round((cur_eq / peak - 1.0) * 100, 2) if peak else 0.0
    # trailing-30d (monthly) return -- equals since-fix until 30 days exist (window is labelled)
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    month_base = next((float(e) for t, e in curve if t >= cutoff), fix_eq)
    month_ret = round((cur_eq / month_base - 1.0) * 100, 2) if month_base else 0.0
    try:
        month_days = min(30, (datetime.now(tz=UTC) - datetime.fromisoformat(fix_ts)).days)
    except ValueError:
        month_days = 0

    recent = con.execute(
        "SELECT ts,symbol,side,qty,status FROM trades ORDER BY ts DESC LIMIT 15").fetchall()
    recent_trades = [{"t": r[0][:19], "symbol": r[1], "side": r[2], "qty": r[3], "status": r[4]}
                     for r in recent]

    step = max(1, len(curve) // 300)
    eq = [{"t": t[:19], "v": round(float(e), 2)} for t, e in curve[::step]]
    out: dict[str, object] = {
        "updated": ts, "mode": mode, "venue": "Binance Futures Testnet",
        "balance": snap["balance"], "equity": pnl["equity"],
        "unrealized_pnl": pnl["unrealized_pnl"],
        "realized_pnl_lifetime": pnl["realized_pnl"],     # account lifetime (incl. pre-fix churn)
        "realized_pnl": realized_fix,                      # SINCE FIX (headline)
        "funding_earned": funding_fix, "win_rate": win_rate,
        "wins": wins, "losses": losses, "n_trades": wins + losses,
        "gross_profit": gross_profit, "gross_loss": gross_loss, "net_since_fix": net_fix,
        "since_fix_start": fix_ts[:19], "since_fix_start_equity": round(fix_eq, 2),
        "start_balance": round(fix_eq, 2),                 # starting balance after the DD-lock fix
        "since_fix_return_pct": since_ret, "since_fix_peak_pct": since_peak,
        "month_return_pct": month_ret, "month_window_days": month_days,
        "peak_equity": round(peak, 2), "drawdown_pct": dd_pct,
        "rolling_sharpe": _curve_sharpe(curve),
        "open_positions": snap["n_target"], "positions": snap.get("positions", []),
        "recent_trades": recent_trades, "maker_share": snap.get("maker_share"),
        "gross_notional": snap["gross_notional"], "gross_leverage": snap["gross_leverage"],
        "equity_curve": eq,
    }
    out.update(extra or {})
    _WEBPERF.write_text(json.dumps(out, indent=2, default=str), "utf-8")


def _round_qty(qty: float, step: float, prec: int) -> float:
    return round(round(qty / step) * step, prec) if step > 0 else round(qty, prec)


def _rebalance(con: sqlite3.Connection, weights: dict[str, float], gross_lev: float,
               max_positions: int, *, dry: bool, band: float = 0.25,
               maker: bool = False, maker_wait: float = 10.0) -> dict[str, object]:
    balance = bt.account_balance() if bt.has_keys() else 15000.0
    prices = bt.mark_prices()
    filters = bt.exchange_filters()
    current = bt.positions() if bt.has_keys() else {}
    gross_notional = balance * gross_lev
    ranked = sorted(weights.items(), key=lambda kv: -abs(kv[1]))[:max_positions]

    target_qty: dict[str, float] = {}
    for sym, w in ranked:
        px, flt = prices.get(sym), filters.get(sym)
        if not px or not flt:
            continue
        raw = (gross_notional * w) / px                       # signed
        q = _round_qty(abs(raw), flt["step"], int(flt["qty_prec"]))
        if q < flt["min_qty"]:
            continue
        target_qty[sym] = q if w > 0 else -q

    orders = []
    ts = datetime.now(tz=UTC).isoformat()
    legs: list[tuple[str, str, float]] = []                    # (symbol, side, qty) to execute
    for sym in sorted(set(target_qty) | set(current)):
        flt = filters.get(sym, {"step": 0.001, "min_qty": 0.0, "qty_prec": 3})
        tgt = target_qty.get(sym, 0.0)
        delta = tgt - current.get(sym, 0.0)
        # NO-TRADE BAND: don't churn a position that's only drifted a little (kills spread bleed).
        # Always allow full exits (tgt == 0). Otherwise require drift > band x target size.
        if tgt != 0.0 and abs(delta) < band * abs(tgt):
            continue
        d = _round_qty(abs(delta), flt["step"], int(flt["qty_prec"]))
        if d < flt["min_qty"]:
            continue
        side = "BUY" if delta > 0 else "SELL"
        if dry:
            orders.append({"symbol": sym, "side": side, "qty": d, "status": "DRY", "mode": "dry"})
        else:
            legs.append((sym, side, d))

    if not dry and legs:
        if maker:
            # MAKER-FIRST: post-only at the passive top-of-book, taker-fallback the unfilled
            modes = maker_execute_batch(legs, filters=filters, book=bt.book_ticker(),
                                        wait_s=maker_wait)
            for sym, side, d in legs:
                mode = modes.get(sym, "taker")
                con.execute("INSERT INTO trades VALUES(?,?,?,?,?,?)",
                            (ts, sym, side, d, "FILLED", mode))
                orders.append({"symbol": sym, "side": side, "qty": d,
                               "status": "FILLED", "mode": mode})
        else:
            for sym, side, d in legs:
                try:
                    res = bt.place_market(sym, side, d)
                    status, detail = str(res.get("status", "?")), str(res.get("orderId", ""))
                except Exception as e:  # log, continue
                    status, detail = "ERROR", repr(e)[:120]
                con.execute("INSERT INTO trades VALUES(?,?,?,?,?,?)",
                            (ts, sym, side, d, status, detail))
                orders.append({"symbol": sym, "side": side, "qty": d,
                               "status": status, "mode": "taker"})
    con.commit()
    gross = sum(abs(q) * prices.get(s, 0.0) for s, q in target_qty.items())
    con.execute("INSERT INTO account VALUES(?,?,?,?)",
                (ts, balance, len(target_qty), gross))
    con.commit()
    # live open positions (pre-trade snapshot) for the desk -- reuses fetched data, no extra calls
    pos_list = sorted(
        ({"symbol": s, "qty": round(q, 4), "side": "LONG" if q > 0 else "SHORT",
          "notional": round(abs(q) * prices.get(s, 0.0), 2)}
         for s, q in current.items() if q != 0.0),
        key=lambda d: -float(d["notional"]))
    filled_modes = {o["symbol"]: str(o.get("mode", "")) for o in orders
                    if o.get("mode") not in (None, "dry")}
    return {"balance": round(balance, 2), "n_target": len(target_qty),
            "gross_notional": round(gross, 2),
            "gross_leverage": round(gross / balance, 2) if balance else 0.0,
            "maker_share": round(maker_share(filled_modes), 2) if filled_modes else None,
            "positions": pos_list, "orders": orders}


def _dd_throttle(equity: float, peak: float) -> float:
    """Cut leverage as drawdown deepens -- deleveraging into a slump caps the drawdown hard while
    keeping full size when winning. The 'max growth, min DD' lever (better than a static cut)."""
    if peak <= 0:
        return 1.0
    dd = equity / peak - 1.0
    if dd >= -0.05:
        return 1.0
    if dd >= -0.10:
        return 0.7
    if dd >= -0.20:
        return 0.4
    return 0.2                                            # deep DD -> ride small until it recovers


def _sync_state(equity: float) -> dict[str, float | str]:
    """Track day/start-equity (daily-loss stop) and peak equity (drawdown throttle) in one file."""
    today = datetime.now(tz=UTC).date().isoformat()
    s = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if s.get("day") != today:
        s["day"] = today
        s["start_equity"] = equity
    s["peak_equity"] = max(float(s.get("peak_equity", equity) or equity), equity)
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(s), "utf-8")
    return s


_MANDATE_DOC = "docs/LAWS.md"
_OVERRIDE_ENV = "QUANT_ALLOW_RETIRED_CRYPTO_CHAIN"


def _mandate_halt() -> str | None:
    """Refuse to run: this executor works ground the canonical universe retired.

    docs/LAWS.md:40-45 makes the full MT5/Fusion universe the desk's sole traded and hunted
    ground. This file is a Binance Futures testnet executor and it also SPAWNS
    `run_daily_research.py` detached, so leaving it runnable kept a whole retired chain one
    invocation away from live -- "not scheduled" was never the same as "cannot run".

    Halting rather than deleting: a deleted file cannot tell anyone why it went, and this one
    still encodes crypto-era execution work worth reading. Same override as the chain it spawns,
    named after the retirement so using it is a deliberate act.
    """
    import os

    if os.environ.get(_OVERRIDE_ENV):
        return None
    root = Path(__file__).resolve().parent.parent
    try:
        text = (root / _MANDATE_DOC).read_text("utf-8")
    except OSError:
        return (f"cannot read {_MANDATE_DOC} to confirm the universe mandate; refusing to run a "
                f"crypto-exchange executor on an unverified mandate (absence is never permission)")
    if "No crypto-exchange-native universe" in text or "MT5/Fusion Markets universe" in text:
        return (f"HALTED BY MANDATE. {_MANDATE_DOC} forbids crypto-exchange-native ground; this "
                f"is a Binance testnet executor and it spawns the retired daily research chain. "
                f"Retired 2026-08-25, preserved for audit.\n"
                f"  To run deliberately for archaeology: {_OVERRIDE_ENV}=1")
    return None


def main() -> None:
    halt = _mandate_halt()
    if halt is not None:
        print(halt)
        raise SystemExit(0)      # a correct refusal is not a failure
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=300.0)
    ap.add_argument("--gross-leverage", type=float, default=3.0,
                    help="gross notional / equity; ~3 = half-Kelly sweet spot, 6 = growth-optimal")
    ap.add_argument("--max-positions", type=int, default=20)
    ap.add_argument("--max-daily-loss", type=float, default=0.25)
    ap.add_argument("--band", type=float, default=0.25, help="no-trade band (drift fraction)")
    ap.add_argument("--no-throttle", action="store_true", help="disable drawdown leverage throttle")
    ap.add_argument("--maker", action="store_true",
                    help="maker-first execution (post-only, taker fallback) -- ~half the fees")
    ap.add_argument("--maker-wait", type=float, default=10.0, help="seconds to rest maker quotes")
    ap.add_argument("--live", action="store_true", help="send orders (default = dry-run)")
    args = ap.parse_args()
    dry = not args.live
    gl = max(0.0, min(args.gross_leverage, 6.0))           # hard cap 6x = the CAGR peak

    if not _TARGET.exists():
        raise SystemExit(f"no target at {_TARGET}; run scripts/run_crypto_target.py")
    weights = {k: float(v) for k, v in json.loads(_TARGET.read_text("utf-8"))["weights"].items()}
    con = _db()
    print(f"BINANCE TESTNET executor | keys={'yes' if bt.has_keys() else 'NO (dry only)'} | "
          f"{'LIVE' if args.live and bt.has_keys() else 'DRY-RUN'} | gross-lev={gl}x | "
          f"{len(weights)} target weights")
    if args.live and not bt.has_keys():
        print("  no testnet keys in env -> staying in dry-run (set BINANCE_TESTNET_KEY/SECRET)")
        dry = True
    if not dry and _another_live_executor():
        raise SystemExit("another LIVE executor is already running (fresh heartbeat) -- exiting")

    forever = args.minutes <= 0                            # --minutes 0 -> persistent loop
    deadline = time.monotonic() + args.minutes * 60.0
    while forever or time.monotonic() < deadline:
        if _KILL.exists():
            print("KILL SWITCH present -> flatten + halt")
            if not dry and bt.has_keys():
                bt.flatten_all()
            break
        try:
            if _cycle(con, weights, gl, args, dry):
                break                                      # daily-loss stop fired
        except Exception as e:  # persistent loop must survive transient network/API errors
            print(f"[{datetime.now(UTC):%H:%M:%S}] cycle error (retrying): {e!r}"[:160])
        time.sleep(args.interval)
    con.close()
    print("testnet session done.")


def _cycle(con: sqlite3.Connection, weights: dict[str, float], gl: float,  # type: ignore
           args, dry: bool) -> bool:
    """One execution cycle; returns True to halt the loop (daily-loss stop)."""
    if not dry:
        _HB.parent.mkdir(parents=True, exist_ok=True)
        _HB.write_text(str(time.time()), "utf-8")          # heartbeat for the single-instance lock
    _daily_data_tasks()                                    # data flywheel rides the always-on loop
    equity = bt.account_summary()["equity"] if bt.has_keys() else 15000.0
    st = _sync_state(equity)
    throttle = 1.0 if args.no_throttle else _dd_throttle(equity, float(st["peak_equity"]))
    regime_mult = _read_regime_mult()                      # HMM regime de-risk overlay (<=1.0)
    gated_base = _read_gated_leverage(gl)                  # edge-gated base (forward-validated)
    eff_gl = round(gated_base * throttle * regime_mult, 2)
    if not dry and equity <= float(st["start_equity"]) * (1.0 - args.max_daily_loss):
        print(f"DAILY LOSS STOP (equity {equity}) -> flatten + halt")
        bt.flatten_all()
        return True
    snap = _rebalance(con, weights, eff_gl, args.max_positions, dry=dry, band=args.band,
                      maker=args.maker, maker_wait=args.maker_wait)
    pnl = {"equity": round(equity, 2), "unrealized_pnl": 0.0, "realized_pnl": 0.0,
           "funding_earned": 0.0}
    if bt.has_keys():
        try:
            acct, inc = bt.account_summary(), bt.income_summary()
            pnl = {"equity": round(acct["equity"], 2),
                   "unrealized_pnl": round(acct["unrealized_pnl"], 2),
                   "realized_pnl": round(inc["realized_pnl"], 2),
                   "funding_earned": round(inc["funding"], 2)}
        except Exception:  # non-fatal: keep last snapshot's sizing view
            pass
    dd = round((equity / float(st["peak_equity"]) - 1.0) * 100, 1)
    ok = sum(1 for o in snap["orders"] if o["status"] in ("DRY", "NEW", "FILLED"))
    print(f"[{datetime.now(UTC):%H:%M:%S}] equity={pnl['equity']} dd={dd}% "
          f"lev={eff_gl}x(x{throttle}) uPnL={pnl['unrealized_pnl']} rPnL={pnl['realized_pnl']} "
          f"gross=${snap['gross_notional']} positions={snap['n_target']} "
          f"orders={len(snap['orders'])} ok={ok}")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "mode": "dry" if dry else "testnet-live",
                                "has_keys": bt.has_keys(), **pnl, **snap}, indent=2), "utf-8")
    start_eq = float(st["start_equity"]) if st.get("start_equity") else equity
    extra = {
        "leverage_cap": gl,
        "leverage_gated_base": gated_base,
        "leverage_target": gated_base,
        "leverage_effective": eff_gl,
        "throttle": throttle,
        "regime_multiplier": regime_mult,
        "leverage_tier": _lev_tier(throttle),
        "kill_switch": _KILL.exists(),
        "daily_return_pct": round((equity / start_eq - 1.0) * 100, 2) if start_eq else 0.0,
        "max_daily_loss_pct": round(args.max_daily_loss * 100, 1),
        "regime": _read_regime(),
    }
    _performance(con, pnl, snap, "dry" if dry else "testnet-live", extra)
    return False


if __name__ == "__main__":
    main()
