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
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_DIR.mkdir(parents=True, exist_ok=True)
LOG = BASE / "logs" / "shadow.log"

from shadow_admission import partition_work  # noqa: E402

SHADOW_START = datetime(2026, 8, 16, tzinfo=UTC)

WINDOWS = {
    "asia": {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13,
                   "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14,
                 "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17,
                   "wait_bars": 8, "rr": 2.0, "ttl_bars": 12},
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
    # MACRO-CONDITIONED, added 2026-08-22. Same session_range_breakout family and the same
    # window params as the unconditioned parent directly above it in this list -- the ONLY
    # difference is that entries are kept solely on days when the symbol's macro driver was
    # falling over the prior 20 days (real 10y yield for metals, DXY for a USD-quoted pair).
    #
    # WHY THESE ARE HERE. Screening (reports/edges_macro_fusion_sweep.json) found the filter
    # RAISES PER-TRADE EXPECTANCY while halving the sample: XAUUSD +0.1603R -> +0.1987R,
    # GBPUSD +0.1184R -> +0.1709R. The t-statistic FALLS in both cases, purely because n
    # halves, which is exactly the shape a screen cannot resolve -- a better filter and a
    # luckier subset look identical in backtest. Forward evidence is the only thing that
    # separates them, so they go to shadow rather than to an argument.
    #
    # PAIRED WITH THEIR PARENTS ON PURPOSE. Each is a strict subset of a sleeve already in
    # this list, so the comparison is against the same family on the same bars over the same
    # window -- the filter's value is the DIFFERENCE, and that is only readable if the parent
    # is accruing beside it. They are here to be measured against those parents, not to be
    # promoted alongside them.
    ("XAUUSD", "asia", "MACRO_FAV"),
    ("XAUUSD", "london_am", "MACRO_FAV"),
    ("XAUUSD", "afternoon", "MACRO_FAV"),
    ("USDJPY", "asia", "MACRO_FAV"),
    ("USDJPY", "london_am", "MACRO_FAV"),
]

#: THE WHOLE-UNIVERSE HALF OF THE DESK. (symbol, family) -- no session window,
#: because these families do not have one.
#:
#: WHY THESE AND NOT THE TOP 47. reports/universe_sweep.json screened 12 families
#: across all 23 symbols and 47 cells cleared the Stage-A bar. Taking all 47 would
#: buy almost nothing: the heat budget scales with sqrt(k_eff), so ten sleeves that
#: fire on the same dollar move are worth about one, and each extra correlated
#: sleeve adds turnover and drawdown without adding capacity. These are the members
#: of the greedy |rho| < 0.30 set -- measured at mean pairwise rho +0.045, k_eff
#: 13.06, which is what lifts the budget from the 9.00% base to the 15% ceiling.
#:
#: SESSION-RANGE ENTRIES ARE DELIBERATELY ABSENT HERE even where they screened
#: highest: XAUUSD, USDJPY, CADJPY, EURJPY and GBPJPY already run that family
#: through SLEEVES above, and listing them again would double-count one mechanism
#: as two sleeves and charge the book twice for the same bet.
#:
#: STAGE A ONLY. Screening decides who gets a forward slot, never who gets capital.
#: 272 cells at t>=1.96 produce false positives by construction; the 14-day/20-trade
#: forward clock is what separates them, and it has not run yet.
UNIVERSE_SLEEVES = [
    ("CADJPY", "fair_value_gap"),        # n=2792 t=4.65 +0.1232R
    ("BTCUSD", "monday_gap"),            # n= 371 t=4.31 +0.3866R
    ("NZDJPY", "dow_effect"),            # n= 892 t=4.18 +0.1940R
    ("GBPJPY", "level_breakout"),        # n=1623 t=4.27 +0.0610R
    ("XAGUSD", "level_breakout"),        # n=1573 t=4.05 +0.0634R
    ("NZDJPY", "fair_value_gap"),        # n=2848 t=3.91 +0.1025R
    ("GBPJPY", "fair_value_gap"),        # n=2715 t=3.83 +0.1025R
    ("CADJPY", "level_breakout"),        # n=1611 t=3.59 +0.0525R
    ("GBPAUD", "session_range_breakout"),  # n=2035 t=4.19 +0.0914R -- not in SLEEVES
    ("GBPUSD", "session_range_breakout"),  # n=2175 t=4.03 +0.1090R -- not in SLEEVES
    ("BTCUSD", "session_range_breakout"),  # n=1765 t=3.69 +0.0899R -- not in SLEEVES
    ("NZDJPY", "session_range_breakout"),  # n=1866 t=3.36 +0.0650R -- not in SLEEVES
]

#: Families UNIVERSE_SLEEVES may name. An explicit ALLOWLIST, not
#: getattr(families, ...) on whatever a sleeve happens to say: a typo must fail
#: as a named wiring error rather than as an AttributeError halfway through a
#: replay, and a sleeve must not be able to reach a family nobody screened.
#:
#: Names, not function objects: `families` is imported inside main() (it pulls
#: pandas/numpy work at import), so resolving here would move that cost to module
#: load and make this file unimportable wherever mt5desk is not on the path --
#: which is precisely where the tests read SLEEVES from.
UNIVERSE_FAMILIES_ALLOWED = frozenset({
    "session_range_breakout", "level_breakout", "fair_value_gap",
    "dow_effect", "monday_gap", "failed_breakout", "order_block",
})


def universe_family(name: str, families_mod):
    """Resolve a UNIVERSE_SLEEVES family name against the allowlist, or None."""
    if name not in UNIVERSE_FAMILIES_ALLOWED:
        return None
    return getattr(families_mod, f"family_{name}", None) or getattr(
        families_mod, {"dow_effect": "family_dow_effect"}.get(name, ""), None)

#: Conditioning values served by the macro history rather than by day_states.
#: Kept as a set so the dispatch in main() is a membership test rather than a
#: string comparison that silently falls through to the day_states branch.
MACRO_CONDS = {"MACRO_FAV"}

#: symbol -> (macro column, lookback days, favourable_sign).
#:
#: THE SIGN IS NOT COSMETIC AND IS THE EASIEST THING HERE TO GET WRONG. -1
#: means a FALLING series is the supportive state; +1 means a RISING one is.
#: Gold rallies as its carry cost falls (-1) and a USD-quoted pair rallies as
#: the dollar falls (-1), but USDJPY is the opposite: it is the DOLLAR that is
#: the base currency, and a RISING US 10y lifts it (+1). Writing USDJPY as -1
#: would filter to precisely the wrong half of history and would not crash,
#: look wrong, or fail a test -- it would produce a clean, confident, inverted
#: number, which is the failure mode run_cot_macro_sweep.py documents at
#: length for the same reason.
MACRO_DRIVER = {
    "XAUUSD": ("REAL_YIELD_10Y", 20, -1),
    "XAGUSD": ("REAL_YIELD_10Y", 20, -1),
    "GBPUSD": ("DXY", 20, -1),
    "USDJPY": ("DGS10", 20, +1),
}


def macro_favourable_dates(sym: str) -> set | None:
    """Dates whose macro driver was in the supportive state for `sym`.

    Returns None when the macro history or the symbol's driver is absent --
    None is NOT an empty set, and the caller must not treat it as "no
    favourable days". An empty set would silently zero the sleeve while
    looking like a legitimate measurement; None makes the caller record NO
    DATA, which is the honest state and the one the promoter can act on.
    """
    from mt5desk import macro_regime

    spec = MACRO_DRIVER.get(sym)
    if spec is None:
        return None
    col, lookback, fav_sign = spec
    hist = macro_regime.load_history()
    if hist is None or col not in hist.columns:
        return None
    s = hist[col].dropna()
    if len(s) < lookback + 2:
        return None
    change = (s - s.shift(lookback)).dropna()
    # PUBLICATION LAG. FRED prints daily market series the following morning,
    # so a value dated D is only knowable from D+1. Shifting the index forward
    # before the join is what keeps this a forward filter rather than a
    # one-day look-ahead applied uniformly across the whole record.
    change.index = pd.to_datetime(change.index) + pd.Timedelta(days=1)
    fav = (change < 0) if fav_sign < 0 else (change > 0)
    return {d.date() for d in fav[fav].index}

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
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(msg + "\n")


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
    from mt5desk.engine import Costs
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

    from research.h1_source import fetch_h1 as _fetch
    start = max(SHADOW_START - timedelta(days=FETCH_DAYS),
                datetime(2018, 1, 1, tzinfo=UTC))
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


def enable_free_feed(state: dict) -> str:
    """Register the free HTTP source -- but ONLY into a record it cannot contaminate.

    **SHADOW HAS BEEN STARVING, NOT FAILING.** Measured 2026-08-20: all 19 sleeves at n=0,
    days_active=0. The replay runs correctly and REFUSES every window, because the only live
    source registered by default is the Windows MT5 terminal, that terminal has been paused for
    the Fusion switch, and the bar cache therefore ends 2026-08-14 -- before SHADOW_START on
    08-16. Shadow is right to refuse: an uncovered window is NO DATA, not a quiet market. But the
    result is that the desk's one source of forward evidence has produced nothing at all while
    five sleeves wait on it, and a day of bars not evaluated cannot be recovered later.

    `h1_source.from_yfinance` exists for exactly this and is deliberately unregistered, because
    turning it on is a decision about evidence quality: those bars are a DIFFERENT SERIES from the
    broker's, and `SourceMix` will call a ledger built from both "an average over two different
    games".

    **THE DECISION IS EASY ONLY BECAUSE THE RECORD IS EMPTY.** With every sleeve at n=0 there is
    no evidence to mix: the record starts homogeneous and stays that way. That is a property of
    today, not a general licence, so it is CHECKED rather than assumed -- if any sleeve has
    accrued rows from a different source this refuses to register and says why. A feed that
    switches mid-record is the failure `SourceMix` was built to name, and it must not be
    introduced by the function meant to keep the record alive.

    The stamp travels regardless: every row carries `HTTP:yfinance/<ticker>`, so a promoter or a
    reader can always see which game the evidence came from.
    """
    from research.h1_source import from_yfinance, register_source

    sleeves = [v for v in state.values() if isinstance(v, dict)]
    accrued = [v for v in sleeves if int(v.get("n", 0) or 0) > 0]
    if accrued:
        srcs = {s for v in accrued for s in (v.get("sources") or {})}
        if not srcs <= {"HTTP:yfinance"} and not all(s.startswith("HTTP:yfinance") for s in srcs):
            return (f"free feed NOT registered: {len(accrued)} sleeve(s) already carry rows from "
                    f"{sorted(srcs) or 'an unrecorded source'}. Registering now would switch the "
                    "feed mid-record and average two different games (SourceMix). Finish the "
                    "broker switch and let MT5 serve these, or start a fresh record.")
    register_source(from_yfinance)
    return ("free feed REGISTERED (HTTP:yfinance) -- the record is empty, so it starts and stays "
            "homogeneous. These are NOT the broker's bars; the stamp says so on every row.")


def main() -> None:
    from mt5desk import families
    from mt5desk.engine import run_backtest

    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    state_path = SHADOW_DIR / "shadow_state.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    slog(enable_free_feed(state))
    attempt_at = datetime.now(UTC).isoformat(timespec="seconds")
    today = datetime.now(UTC).date().isoformat()

    h1_cache = {}
    # SLEEVES rows are (sym, window, cond) and always session_range_breakout.
    # UNIVERSE_SLEEVES rows are (sym, family) -- a different shape because they
    # are a different thing, and flattening them into one list would have made
    # `window` meaningless for families that have no session window at all.
    # Normalised here into one loop rather than duplicating the body.
    _declared = [(s, w, c, "session_range_breakout", False) for s, w, c in SLEEVES]
    _declared += [(s, f, None, f, True) for s, f in UNIVERSE_SLEEVES]
    _work, _blocked = partition_work(_declared, BASE)
    quarantine = {}
    for sym, selector, cond, _fam, _is_universe in _blocked:
        key = f"{sym}.{selector}" + (f".{cond}" if cond else "")
        st = state.pop(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None})
        st.update({
            "status": "QUARANTINED_UNCERTIFIED",
            "promotion_authority": False,
            "gate_admission": "BLOCKED",
            "gate_reason": "missing exact original universal ten-gate pass",
            "last_attempt_at": attempt_at,
        })
        quarantine[key] = st
    # Uncertified historical rows are preserved for diagnosis, but they are not
    # shadow sleeves. Keeping them in shadow_state made a zero-authority research
    # backlog appear as 36 active sleeves and allowed stale dashboards to report
    # a promotion-bearing pool that did not exist.
    (SHADOW_DIR / "shadow_quarantine.json").write_text(json.dumps({
        "updated_at": attempt_at,
        "reason": "missing exact original universal ten-gate pass",
        "candidates": quarantine,
    }, indent=2), encoding="utf-8")
    (SHADOW_DIR / "shadow_admission.json").write_text(json.dumps({
        "at": attempt_at,
        "policy": "mt5-original-universal-10-v2-calibrated-inputs",
        "declared": len(_declared),
        "admitted": len(_work),
        "blocked": len(_blocked),
        "blocked_keys": [f"{s}.{w}" + (f".{c}" if c else "")
                         for s, w, c, _f, _u in _blocked],
    }, indent=2), encoding="utf-8")
    for sym, win, cond, fam, is_universe in _work:
        key = f"{sym}.{win}" + (f".{cond}" if cond else "")
        st = state.get(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None,
                             "status": "ACTIVE"})
        st["last_attempt_at"] = attempt_at
        st["gate_admission"] = "ORIGINAL_UNIVERSAL_10_PASS"
        if st.get("status") == "BLOCKED_UNIVERSAL_GATES":
            st["status"] = "ACTIVE"
        if sym not in h1_cache:
            h1_cache[sym] = fetch_h1(sym)
        bars = h1_cache[sym]
        if bars is None:
            # RECORDED, not skipped. A sleeve that produced nothing because there
            # were no bars is a different fact from one that stood aside, and the
            # promoter must not count the first as evidence of the second.
            if st.get("last_no_data") != today:
                st["no_data_days"] = int(st.get("no_data_days", 0)) + 1
            st["last_no_data"] = today
            if st.get("status") not in {"KILL", "PROMOTION CANDIDATE"}:
                st["status"] = "NO_DATA"
            state[key] = st
            continue
        h1 = bars.df
        if st.get("status") in {"NO_DATA", "PROXY_SHADOW"}:
            st["status"] = "ACTIVE"
        if fam == "session_range_breakout" and not is_universe:
            sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        else:
            fn = universe_family(fam, families)
            if fn is None:
                # NOT a silent skip. A sleeve naming a family this module cannot
                # build is a wiring error, and recording it as "no data" would
                # hide it behind the same counter that means "the feed was down".
                slog(f"{key}: UNKNOWN FAMILY {fam!r} -- sleeve cannot be replayed")
                st["last_error"] = f"unknown family {fam}"
                state[key] = st
                continue
            sigs = fn(h1)
        if cond in MACRO_CONDS:
            fav = macro_favourable_dates(sym)
            if fav is None:
                # NO DATA, recorded as such. Distinct from "the macro state stood
                # aside": one is a missing input, the other is evidence. Collapsing
                # them is the defect this file already guards against for bars.
                if st.get("last_no_data") != today:
                    st["no_data_days"] = int(st.get("no_data_days", 0)) + 1
                st["last_no_data"] = today
                if st.get("status") not in {"KILL", "PROMOTION CANDIDATE"}:
                    st["status"] = "NO_DATA"
                state[key] = st
                continue
            sigs = [g for g in sigs if pd.Timestamp(g.time).date() in fav]
        elif cond:
            # Same corrected prior-day join the sweep used. A shadow record built on a different
            # conditioning rule than the backtest would be measuring a third strategy.
            from run_hunt12 import day_states
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
        st["promotion_authority"] = bars.promotion_authority
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
            days_active = (datetime.now(UTC) -
                           pd.Timestamp(st["first_entry"]).to_pydatetime().replace(tzinfo=UTC)).days
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
                if bars.promotion_authority:
                    st["status"] = "PROMOTION CANDIDATE"
                    slog(f"{key}: VERDICT PROMOTE n={st['n']} exp={st['exp_r']:.3f}R "
                         f"maxDD={st['max_dd_r']:.1f}R")
                else:
                    st["status"] = "PROXY_SHADOW"
                    st["proxy_verdict"] = "WOULD_PROMOTE_ON_MATCHING_FUSION_EVIDENCE"
                    slog(f"{key}: proxy evidence passes numerically, but {bars.source} has no "
                         "Fusion capital authority; continue shadow")
            else:
                st["status"] = "KILL"
                slog(f"{key}: VERDICT KILL n={st['n']} exp={st['exp_r']:.3f}R "
                     f"maxDD={st['max_dd_r']:.1f}R")
        state[key] = st
        slog(f"{key}: shadow n={st['n']} cumR={st['cum_r']:+.2f} "
             f"exp={st['exp_r']:+.3f}R maxDD={st['max_dd_r']:.1f}R "
             f"days={days_active} [{st['status']}]")
    state["last_run"] = today
    state["updated_at"] = attempt_at
    state["declared_sleeves"] = len(_declared)
    state["configured_sleeves"] = len(_work)
    state["gate_blocked_sleeves"] = len(_blocked)
    state["represented_sleeves"] = sum(
        isinstance(v, dict) for k, v in state.items()
        if k not in {"last_run", "updated_at", "declared_sleeves", "configured_sleeves",
                     "gate_blocked_sleeves", "represented_sleeves"}
    )
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    slog(f"shadow state saved ({len(_work)} configured sleeves)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        slog("shadow error:", traceback.format_exc())
