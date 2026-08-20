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

# (sym, window, state) -- state=None means UNCONDITIONED, the hunt6 form.
#
# A THIRD FIELD WAS ADDED, and it had to be added here, in the promoter and in the gateway at the
# same time. Before this the live chain was state-blind end to end: this list keyed on
# (symbol, window), promoter wrote no state, and gateway.sleeve_set rebuilt every sleeve from the
# window alone. Promoting "CADJPY asia FAILED_BREAK" would therefore have traded CADJPY asia on
# EVERY day -- the sleeve carrying the name and risk budget of a strategy that earned +0.276R
# while actually running the unconditioned one at +0.163R, with nothing anywhere saying so.
SLEEVES = [
    # hunt6 survivors, unconditioned
    ("XAUUSD", "asia", None), ("XAUUSD", "london_am", None), ("XAUUSD", "afternoon", None),
    ("USDJPY", "asia", None), ("USDJPY", "london_am", None),
    ("CADJPY", "asia", None),
    ("EURJPY", "asia", None), ("EURJPY", "london_am", None),
    ("GBPJPY", "asia", None), ("GBPJPY", "london_am", None),
    # hunt12 candidates, state-conditioned, added 2026-08-17 after the day_states lookahead fix.
    # These FAILED the 10-gate gauntlet on deflated Sharpe (SR0 0.471 against 0.138-0.256 at
    # n_trials 2,464) and pass the other nine. That is a POWER problem, not a validity one -- PBO
    # 0.034 and walk-forward stability 1.0 say they are not curve-fits -- and forward evidence is
    # the only thing that can settle it. Shadow generates exactly that, at zero capital.
    # The three XAUUSD entries are filtered subsets of gold legs already live: they are here to be
    # MEASURED against their parent, not to be promoted alongside it.
    ("CADJPY", "asia", "FAILED_BREAK"),
    ("USDJPY", "asia", "FAILED_BREAK"),
    ("EURJPY", "asia", "FAILED_BREAK"),
    ("EURJPY", "asia", "NORMAL_DAY"),
    ("CADJPY", "london_am", "NORMAL_DAY"),
    ("USDJPY", "london_am", "FAILED_BREAK"),
    ("XAUUSD", "asia", "NORMAL_DAY"),
    ("XAUUSD", "asia", "FAILED_BREAK"),
    ("XAUUSD", "london_am", "NORMAL_DAY"),
]

FETCH_DAYS = 45
VERDICT_MIN_TRADES = 50
VERDICT_MIN_DAYS = 14
PROMOTE_MIN_EXP = 0.05
PROMOTE_MIN_DD = -25.0

#: Trades below which NO terminal verdict is issued, in either direction. The 14-day clock still
#: runs -- it just cannot execute a sleeve on three fills. 20 is where the false-kill rate on a
#: genuinely good edge falls under 20% (36% at n=3); it is a floor on evidence, not a target.
#: Raising it makes the desk slower and more certain, lowering it faster and more arbitrary.
MIN_VERDICT_TRADES = 20


def slog(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def per_symbol_costs(meta: dict, sym: str):
    """R0644 / GAP 114 ON THE PROMOTION PATH -- the worst place this bug had a copy.

    Until 2026-08-20 this read:

        spread = 0.48 if sym == "XAUUSD" else (
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"])
        return Costs(spread_per_lot=max(spread, 0.05), commission_per_lot=3.50, ...)

    Two defects, and shadow is where they mattered most:

      GOLD AT 3% OF ITS SPREAD. 0.48 is dollars per OUNCE in a field that wants dollars per LOT.
      The engine divides by contract_size 100 and charges 0.0048/oz against a measured 0.16/oz
      median. `calibrate_engine.py` puts a number on it with a known-answer probe: the constant
      recovers 0.2099x of the planted cost and FAILS; `from_symbol` recovers 0.9166x and passes.

      EVERY OTHER SYMBOL AT mult=1.0 -- the spread crossed once, where a round trip crosses it
      going in and again coming out.

    **THIS IS THE DOOR TO CAPITAL, NOT A RESEARCH SCRIPT.** Shadow's verdict thresholds are
    `exp_r > 0.05R` -> PROMOTION CANDIDATE, `max_dd_r > -25R`. A gold sleeve judged nearly
    spread-free clears 0.05R on costs it will never actually pay, and the promoter -- which is
    automatic and correctly refuses hand-editing -- acts on that verdict. The protocol's whole
    design is that one door is hard to get through; a mispriced cost model widens it silently.

    **EXISTING SHADOW RECORDS WERE ACCRUED AT THE OLD COSTS** and their expectancies are upper
    bounds. They are not deleted here -- a shadow record is forward evidence and destroying it to
    tidy a cost change would cost the one thing that cannot be recovered later -- but any verdict
    resting on them must be re-derived before it promotes anything.
    """
    from mt5desk.engine import Costs  # noqa: PLC0415
    return Costs.from_symbol(meta[sym], mult=2.0)


def fetch_h1(sym: str):
    """Bars from whatever source is available, with the provenance attached.

    THIS IMPORTED MetaTrader5 DIRECTLY, which made the entire shadow record
    hostage to a Windows box with a logged-in terminal. When the Fusion switch
    paused that terminal, shadow stopped, and the daily cycle has failed on
    ModuleNotFoundError ever since -- losing the one thing that cannot be
    recovered later, because a day of bars not evaluated is a day of evidence
    gone.

    Shadow needs bars and nothing else: no terminal, no login, no funded
    account, no accepted order. See research/h1_source.py.

    Returns a `Bars` (not a DataFrame) so the source travels with the data.
    """
    from datetime import timedelta

    from research.h1_source import fetch_h1 as _fetch  # noqa: PLC0415
    start = max(SHADOW_START - timedelta(days=FETCH_DAYS),
                datetime(2018, 1, 1, tzinfo=timezone.utc))
    bars = _fetch(sym, start)
    if bars is None:
        slog(f"{sym}: NO DATA from any source. That is an absence of bars, not "
             f"an empty market, and no verdict may be drawn from it.")
        return None
    ok, why = bars.covers(SHADOW_START)
    slog(f"{sym}: {bars.n} bars from {bars.source} -- {why}")
    if not ok:
        # NOT a silent continue. Replaying a window the source does not cover
        # records "no trades" for days there was simply no data, which is
        # indistinguishable from a strategy standing aside and inflates the
        # denominator of every rate the promoter computes.
        slog(f"{sym}: REFUSING to replay an uncovered window -- {why}")
        return None
    if bars.stale:
        slog(f"{sym}: source is STALE ({bars.age_hours:.1f}h old). Recorded, and "
             f"the stamp travels with every row.")
    return bars


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
    for sym, win, cond in SLEEVES:
        key = f"{sym}.{win}" + (f".{cond}" if cond else "")
        st = state.get(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None,
                             "status": "ACTIVE"})
        if sym not in h1_cache:
            h1_cache[sym] = fetch_h1(sym)
        bars = h1_cache[sym]
        if bars is None:
            # RECORDED, not skipped. A sleeve that produced nothing because there
            # were no bars is a different fact from one that stood aside, and the
            # promoter must not count the first as evidence of the second.
            st["last_no_data"] = today
            st["no_data_days"] = int(st.get("no_data_days", 0)) + 1
            state[key] = st
            continue
        h1 = bars.df
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        if cond:
            # Same corrected prior-day join the sweep used. A shadow record built on a different
            # conditioning rule than the backtest would be measuring a third strategy.
            from run_hunt12 import day_states  # noqa: PLC0415
            st_map = day_states(h1)
            sigs = [g for g in sigs if st_map.get(pd.Timestamp(g.time).date()) == cond]
        res = run_backtest(h1, sigs, per_symbol_costs(meta, sym))
        trades = [t for t in res.trades if t.entry_time >= SHADOW_START]
        ledger = SHADOW_DIR / (f"ledger_{sym}_{win}" + (f"_{cond}" if cond else "") + ".json")
        # THE SOURCE STAMP TRAVELS WITH EVERY ROW. A trade replayed on a broker
        # feed and one replayed on cached or free bars are not the same evidence
        # -- OHLC differ at the tick and spreads differ materially -- so an
        # expectancy averaged across them is an average over two different
        # games. Stamped per row so the promoter can split them.
        _stamp = bars.stamp()
        ledger.write_text(json.dumps(
            [{"entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
              "side": t.side, "entry": t.entry, "exit": t.exit,
              "r_multiple": t.r_multiple, "reason": t.reason, **_stamp}
             for t in trades],
            indent=2), encoding="utf-8")
        st["bar_source"] = bars.source
        st["bar_source_stale"] = bars.stale
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
        # NO TERMINAL VERDICT WITHOUT ENOUGH EVIDENCE TO SUPPORT ONE.
        #
        # This fired on `n >= 50 OR days_active >= 14`, and the days clause is what did the
        # damage. A cell firing ~80 times a year produces about THREE trades in fourteen days,
        # and the verdict is permanent in both directions. Measured against the best candidate's
        # +0.276R with per-trade sd 1.089, the chance of KILLING a genuinely good edge:
        #
        #        3 trades -> 36.0%          20 trades -> 17.7%
        #        5        -> 32.1%          50        ->  7.1%
        #       10        -> 25.6%         100        ->  1.9%
        #
        # So the clock was not rescuing slow sleeves from limbo -- it was executing them at
        # random, and the same arithmetic promotes noise in the other direction. The fix is not a
        # looser clock but refusing to decide early: below MIN_VERDICT_TRADES the sleeve stays
        # ACTIVE and keeps accruing, which costs nothing because shadow uses no capital. A slow
        # edge is then never stuck (it promotes the moment it has evidence) and never killed on
        # three fills.
        if st["status"] == "ACTIVE" and (st["n"] >= VERDICT_MIN_TRADES
                                         or days_active >= VERDICT_MIN_DAYS):
            if st["n"] < MIN_VERDICT_TRADES:
                slog(f"{key}: verdict DEFERRED -- n={st['n']} < {MIN_VERDICT_TRADES} after "
                     f"{days_active}d. Deciding on this sample is more likely to be wrong than "
                     f"right; sleeve stays ACTIVE and keeps accruing.")
            elif st["exp_r"] > PROMOTE_MIN_EXP and st["max_dd_r"] > PROMOTE_MIN_DD:
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