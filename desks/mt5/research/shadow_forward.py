"""Shadow-forward validation for hunt6 survivors (10 sleeves).

Deterministic replay on real live H1 bars from SHADOW_START forward. Same
families/engine code as the backtest -> identical signals given identical bars.
No capital: fills simulated at actual bar opens with the account cost model.

Ledger: reports/shadow/ledger_<sym>_<window>.json (full trade list, idempotent).
State:  reports/shadow/shadow_state.json (per sleeve n / cumR / exp / maxDD /
days / status; runs once per UTC day).

Verdict at n>=50 or 14 days active: exp>0.05R and maxDD>-25R -> PROMOTION
CANDIDATE (portfolio study + sizing before any live lot), else KILL.
XAUUSD sleeves here are challengers (hunt6 generic params) vs the armed
hunt5-param gold book.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_DIR.mkdir(parents=True, exist_ok=True)
LOG = open(BASE / "logs" / "shadow.log", "a", encoding="utf-8")

SHADOW_START = datetime(2026, 8, 16, tzinfo=timezone.utc)

WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}

SLEEVES = [  # (sym, window) - hunt6 survivors
    ("XAUUSD", "asia"), ("XAUUSD", "london_am"), ("XAUUSD", "afternoon"),
    ("USDJPY", "asia"), ("USDJPY", "london_am"),
    ("CADJPY", "asia"),
    ("EURJPY", "asia"), ("EURJPY", "london_am"),
    ("GBPJPY", "asia"), ("GBPJPY", "london_am"),
]

FETCH_DAYS = 45
VERDICT_MIN_TRADES = 50
VERDICT_MIN_DAYS = 14
PROMOTE_MIN_EXP = 0.05
PROMOTE_MIN_DD = -25.0


def slog(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def per_symbol_costs(meta: dict, sym: str):
    from mt5desk.engine import Costs  # noqa: E402
    m = meta[sym]
    spread = 0.48 if sym == "XAUUSD" else (
        m["median_spread_pts"] * m["tick_size"] * m["contract_size"])
    return Costs(spread_per_lot=max(spread, 0.05),
                 commission_per_lot=3.50, contract_oz=m["contract_size"])


def fetch_h1(sym: str) -> pd.DataFrame | None:
    import MetaTrader5 as mt5  # noqa: E402
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"):
            slog(f"mt5 init failed: {mt5.last_error()}")
            return None
    from datetime import timedelta
    start = max(SHADOW_START - timedelta(days=FETCH_DAYS),
                datetime(2018, 1, 1, tzinfo=timezone.utc))
    rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, start, datetime.now(timezone.utc))
    if rates is None or len(rates) < 100:
        slog(f"{sym}: no fresh H1 ({0 if rates is None else len(rates)} bars)")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.set_index("time").sort_index()[["open", "high", "low", "close",
                                              "tick_volume", "spread", "real_volume"]]


def main() -> None:
    from mt5desk import families  # noqa: E402
    from mt5desk.engine import run_backtest  # noqa: E402

    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    state_path = SHADOW_DIR / "shadow_state.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("last_run") == today:
        slog("shadow already ran today; skip")
        return

    h1_cache = {}
    for sym, win in SLEEVES:
        key = f"{sym}.{win}"
        st = state.get(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None,
                             "status": "ACTIVE"})
        if sym not in h1_cache:
            h1_cache[sym] = fetch_h1(sym)
        h1 = h1_cache[sym]
        if h1 is None:
            continue
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        res = run_backtest(h1, sigs, per_symbol_costs(meta, sym))
        trades = [t for t in res.trades if t.entry_time >= SHADOW_START]
        ledger = SHADOW_DIR / f"ledger_{sym}_{win}.json"
        ledger.write_text(json.dumps(
            [{"entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
              "side": t.side, "entry": t.entry, "exit": t.exit,
              "r_multiple": t.r_multiple, "reason": t.reason} for t in trades],
            indent=2), encoding="utf-8")
        if trades:
            rs = [t.r_multiple for t in trades]
            cum = [sum(rs[:i + 1]) for i in range(len(rs))]
            max_dd = min(cum[i] - max(cum[:i + 1]) for i in range(len(cum)))
            st.update({
                "n": len(trades), "cum_r": float(sum(rs)),
                "exp_r": float(sum(rs) / len(rs)),
                "max_dd_r": float(max_dd),
                "first_entry": str(trades[0].entry_time),
                "last_entry": str(trades[-1].entry_time),
            })
        else:
            st.setdefault("exp_r", 0.0)
        days_active = 0
        if st.get("first_entry"):
            days_active = (datetime.now(timezone.utc) -
                           pd.Timestamp(st["first_entry"]).to_pydatetime().replace(tzinfo=timezone.utc)).days
        st["days_active"] = days_active
        if st["status"] == "ACTIVE" and (st["n"] >= VERDICT_MIN_TRADES
                                         or days_active >= VERDICT_MIN_DAYS):
            if st["exp_r"] > PROMOTE_MIN_EXP and st["max_dd_r"] > PROMOTE_MIN_DD:
                st["status"] = "PROMOTION CANDIDATE"
                slog(f"{key}: VERDICT PROMOTE n={st['n']} exp={st['exp_r']:.3f}R "
                     f"maxDD={st['max_dd_r']:.1f}R")
            else:
                st["status"] = "KILL"
                slog(f"{key}: VERDICT KILL n={st['n']} exp={st['exp_r']:.3f}R "
                     f"maxDD={st['max_dd_r']:.1f}R")
        state[key] = st
        slog(f"{key}: shadow n={st['n']} cumR={st['cum_r']:+.2f} "
             f"exp={st['exp_r']:+.3f}R maxDD={st['max_dd_r']:.1f}R "
             f"days={days_active} [{st['status']}]")
    state["last_run"] = today
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    slog(f"shadow state saved ({len(SLEEVES)} sleeves)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        slog("shadow error:", traceback.format_exc())