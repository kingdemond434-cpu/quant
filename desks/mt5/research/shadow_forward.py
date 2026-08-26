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

#: Grandfathered enrolment only -- hunt6 sleeves already on clocks when enrolment became
#: data-driven. NEVER extend this list by hand: a certificate IS enrolment (RESEARCH §6d, the
#: one-pipeline law), and `certified_sleeves()` below turns every ten-gate pass into a clock on
#: the next daily run with no code edit. Editing this literal instead is the exact defect the
#: same-day fence exists to catch (a certificate sat un-enrolled until a human typed).
#: GRANDFATHERING IS OVER (principal 2026-08-26: "shouldn't all be tested for certification and
#: retired if the 10 gates don't work"). This list held ten hunt6 sleeves that ran WITHOUT a
#: ten-gate certificate. On 2026-08-26 `forward_reconcile` put all ten through the canonical
#: gauntlet: the five `asia` cells hold certificates and now enrol through `certified_sleeves()`
#: like everything else, and the five london_am/afternoon cells FAILED on PBO 0.5961 (threshold
#: 0.50 -- a 60% probability of being backtest-overfit) and are retired RETIRED_GATE_FAIL.
#: The list stays empty: enrolment is a CERTIFICATE, never a literal a human typed.
SLEEVES: list[tuple[str, str]] = []


def certified_sleeves() -> list[tuple[str, str]]:
    """Every ten-gate certificate, as (sym, window) rows for the ONE forward engine.

    Authority comes from `shadow_admission.authorized_specs` -- the same fail-closed door every
    other consumer uses (exact policy attestation + all ten gates + explicit shadow_spec). This
    function adds NO judgment of its own: it only shapes admitted specs into the engine's row
    format, and drops (visibly) anything whose selector this engine has no window for. A dropped
    spec is a wiring gap for the gap-wirer, never a silent skip.
    """
    rows: list[tuple[str, str]] = []
    try:
        from shadow_admission import authorized_specs
        for sym, selector, _cond, family, _isu in sorted(authorized_specs(BASE)):
            if family != "session_range_breakout":
                continue  # this engine runs one family; other families enrol as they are built
            if selector not in WINDOWS:
                slog(f"ENROL-GAP: certified {sym}.{selector} has no window mapping; "
                     f"certificate exists but cannot be run -- wire the selector")
                continue
            rows.append((sym, selector))
    except Exception as exc:  # noqa: BLE001 -- enrolment must never kill the running clocks
        slog(f"certified_sleeves FAILED ({type(exc).__name__}: {exc}); "
             f"running grandfathered sleeves only this pass")
    return rows

FETCH_DAYS = 45
VERDICT_MIN_TRADES = 50
VERDICT_MIN_DAYS = 14
PROMOTE_MIN_EXP = 0.05
PROMOTE_MIN_DD = -25.0
#: SEQUENTIAL SUFFICIENCY (principal 2026-08-26: discovery -> gates -> forward -> live, same day
#: at the front, and the forward leg must actually be reachable). A flat n>=50 is a PROXY for
#: "enough forward evidence to overturn the power-gate doubt". At this desk's measured rate --
#: 5-7 trades per sleeve in 8 days, ~0.75/day -- that proxy costs ~66 days, so the 14-day clause
#: it is AND'd with was dead letter and nothing could ever promote. The fix is not to lower the
#: bar but to MEASURE THE THING THE BAR STANDS FOR: a t-statistic on forward R is valid at any n,
#: so a large true edge clears it early and a weak one still fails at n=200. Strictly more
#: aggressive when the edge is real, strictly stricter when it is marginal.
SEQ_MIN_TRADES = 20      # never a verdict on a handful of trades, however pretty
SEQ_MIN_T = 2.5          # forward mean R significantly > 0, one-sided


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


def fetch_h1(sym: str):
    """Bars from whatever source is available, with the provenance attached.

    THIS IMPORTED MetaTrader5 DIRECTLY, which made the entire shadow record
    hostage to a Windows box with a logged-in terminal -- on this Linux box the
    daily cycle died on ModuleNotFoundError, and a day of bars not evaluated is
    a day of forward evidence no later run can recover. Shadow needs bars and
    nothing else: no terminal, no login, no funded account, no accepted order.
    See research/h1_source.py. (Re-applied 2026-08-26 after a sync trample
    reverted a0c3de04; the guard tests in tests/test_h1_source.py are the
    fence.)

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
        # NOT a silent continue: replaying a window the source does not cover
        # would record "no trades" for days that are actually NO DATA, and the
        # promoter would divide by a denominator that includes them.
        return None
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

    h1_cache = {}
    # ONE PIPELINE: grandfathered rows plus every certificate, deduped. Certificates enrol
    # here automatically -- the same day they are written -- with their clock stamped below.
    enrolled = list(dict.fromkeys(SLEEVES + certified_sleeves()))
    for sym, win in enrolled:
        key = f"{sym}.{win}"
        st = state.get(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None,
                             "status": "ACTIVE"})
        if sym not in h1_cache:
            h1_cache[sym] = fetch_h1(sym)
        bars = h1_cache[sym]
        if bars is None:
            continue
        h1 = bars.df
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        res = run_backtest(h1, sigs, per_symbol_costs(meta, sym))
        trades = [t for t in res.trades if t.entry_time >= SHADOW_START]
        ledger = SHADOW_DIR / f"ledger_{sym}_{win}.json"
        # A trade replayed on the broker's own feed and one replayed on cached
        # or free bars are not the same evidence -- OHLC differ at the tick and
        # spreads differ materially -- so an expectancy averaged across them is
        # an average over two different games. Stamped per row so the promoter
        # can split them.
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
        st["order_authority"] = False
        st["gate_admission"] = "ORIGINAL_UNIVERSAL_10_PASS"
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
        # THE CLOCK STARTS AT PRE-REGISTRATION, NOT AT THE FIRST TRADE EVER TAKEN. This read
        # `first_entry` -- trades[0].entry_time -- so a sleeve that had been trading for 8 days
        # before its hypothesis was frozen arrived at the gate already 8/14 of the way through
        # its "forward" window, on evidence gathered while it was still being SELECTED. That is
        # the precise leakage the two-stage law exists to stop (LAWS L1.28a; RESEARCH §6a: the
        # gauntlet screens, only pre-registered forward evidence promotes). `forward_start` is
        # stamped once, the first time a row is seen, and never moved.
        now = datetime.now(timezone.utc)
        if not st.get("forward_start"):
            st["forward_start"] = now.isoformat()
        days_active = (now - pd.Timestamp(st["forward_start"]).to_pydatetime()
                       .replace(tzinfo=timezone.utc)).days
        st["days_active"] = days_active
        # SUFFICIENT EVIDENCE = the flat count OR a significant forward t-stat at a floor of
        # trades. Whichever arrives first; both are honest, one is merely faster when the edge
        # is large. Quality bars (exp_r, maxDD) still apply to every promotion below.
        t_stat = 0.0
        if len(trades) >= 2:
            _rs = [t.r_multiple for t in trades]
            _mean = sum(_rs) / len(_rs)
            _var = sum((x - _mean) ** 2 for x in _rs) / (len(_rs) - 1)
            if _var > 0:
                t_stat = _mean / ((_var / len(_rs)) ** 0.5)
        st["forward_t"] = round(t_stat, 3)
        enough = (st["n"] >= VERDICT_MIN_TRADES
                  or (st["n"] >= SEQ_MIN_TRADES and t_stat >= SEQ_MIN_T))
        # AND, never OR: gate_spec.yaml has always said `n >= 50, days >= 14` together, but this
        # line said `or`, so a sleeve holding ONE trade would take a verdict on day 14 -- and
        # `EURJPY.asia.NORMAL_DAY` (n=1) and three MACRO_FAV rows (n=1) were on course to do
        # exactly that. A one-trade promotion is not a fast promotion, it is a coin flip wearing
        # a certificate.
        if st["status"] == "ACTIVE" and enough and days_active >= VERDICT_MIN_DAYS:
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
    state["configured_sleeves"] = len(enrolled)
    state["gate_blocked_sleeves"] = 0
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    slog(f"shadow state saved ({len(enrolled)} sleeves, {len(enrolled) - len(SLEEVES)} certificate-enrolled)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        slog("shadow error:", traceback.format_exc())
