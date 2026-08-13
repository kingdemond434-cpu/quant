"""Daily trade-class forensics -- the mechanical version of the probes that found gaps #42/#43/#34.

On 2026-07-22 the principal's manual pushing surfaced three profit leaks the cycle had missed:
churn drag (-8.1%/yr in sub-8h holds), baseline-funding entries (-92.7 bps, ~80% of gross profit),
and concentrated leg-thrash losses. All three were visible in ONE artifact the desk already owned
-- data/cashcarry_trades.json -- bucketed three ways. Per the RECURSION RULE, that analysis is now
a standing daily check: pure python, quota-free, runs even when the brain is auth-dead (as it was
the day this was written). Writes web/trade_forensics.json (the executor's denylist source) plus a
tracked copy at docs/research/trade_forensics_latest.json; run_alerts pages on any bleeding class.

    python scripts/run_trade_forensics.py
"""
from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
# the artifact, where an error string is indistinguishable from data to every reader downstream.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.execution import leg_modes
from libs.ops.desk_host import is_owning_host

_TRADES = Path("data/cashcarry_trades.json")
_OUT = Path("web/trade_forensics.json")
# A MODULE CONSTANT so a test can inject one (2026-08-13). This was a local inside main(), so the
# entry-gate detector's only test read the LIVE desk cost model: it asserted a BNBUSDT open was
# flagged, the measured book got cheaper (0.344 bps pair round-trip at that size), and the test
# went red for a reason having nothing to do with the behaviour it pins. A test that fails when
# the desk's state moves teaches readers to discount red -- which is how the merge-union defect
# this file's `bleeding_symbols` key repairs stayed invisible for eight days.
_COST_MODEL = Path("data/cost_model.json")
# web/ is untracked runtime state: evidence that exists ONLY there is invisible to any checkout
# and unciteable by an audit (R0160). _TRACKED is the governed, reports-parallel copy of the same
# doc; run_cashcarry_executor keeps reading _OUT -- the denylist read path must not move.
_TRACKED = Path("docs/research/trade_forensics_latest.json")
_MIN_N = 15            # a class needs this many trades before its verdict is trusted
_WINDOW_D = 14.0       # ROLLING window: all-history flags would re-page forever even
                       # after fixes work; the question is "is it bleeding NOW"
_BLEED_BPS = -1.0      # class net worse than this (bps of notional) = defect
# DENYLIST EVIDENCE IS ALL-TIME, ALERTS ARE ROLLING (2026-08-05, restored 2026-08-13). These
# mirror the executor's `_BLEED_BPS`/`_BLEED_MIN_N`; the mirror exists because importing the
# executor opens venue connections, so tests/execution/test_carry_entry_gate.py asserts the two
# pairs stay equal and drift fails CI instead of silently re-blinding the fence.
_DENY_BPS = -20.0      # all-time realised net bps at which a symbol is structurally bleeding
_DENY_MIN_N = 5        # minimum closed trades before that verdict is trusted
_FEE_RT_BPS = 10.0     # futures leg billed twice per round-trip at ~5 bps taker rack rate
_FEE_BPS_MAX = 50.0    # 5x that -- generous for maker/taker mix + partials, so anything above
                       # is fills the book never intended, not an execution-quality gradient
_BASELINE = 0.000100   # Binance default funding -- carries no premium information by itself
# entry-gate ship time. The CONTRACT CHANGED 2026-07-31 (R0057): the absolute funding floor was
# deleted in favour of the executor's per-symbol arithmetic -- allow an open iff
# funding * 1e4 * periods > pair_roundtrip_bps, periods = max(1, _MIN_HOLD_H/8) = 3. A baseline
# open on a tight measured major (BTC rt < 3 bps) is that design WORKING; flagging every
# baseline open forever re-litigates a ledgered decision and turns this flag into a
# permanently-red light nobody reads (L1.43). The regression test below now mirrors the
# executor's modelled cost (bucket-by-notional, legacy-500 fallback, p90 fail-closed default for
# unmeasured names). KNOWN LOOSER EDGE, deliberate and named: the executor additionally floors
# the model with each symbol's REALISED round-trip, which this reader cannot reconstruct -- so
# this detector can under-fire only where realised costs exceed modelled. The durable close is
# the executor stamping its gate arithmetic on the open row (rowed; blocked behind the pending
# executor-lineage merge -- see F0021).
_GATE_DATE = "2026-07-22T20:00:00+00:00"
_GATE_PERIODS = 3.0             # max(1, 24h min-hold / 8h funding period)
_GATE_DEFAULT_RT_BPS = 39.5     # p90 of measured round-trips; fail-closed for unmeasured names


def _gate_rt_bps(sym: str, notional: float, cost_model: dict[str, Any]) -> float:
    """Modelled pair round-trip for the entry-gate mirror. Bucket covering the per-leg notional,
    legacy-500 fallback, larger buckets clamped tighten-only vs 500 -- the executor's _rt_bps
    minus its realised floor (unavailable here; direction of the gap is documented above)."""
    try:
        pair = cost_model["symbols"][sym]["pair"]
        sizes = sorted(float(k) for k in pair)
        key = next((k for k in sizes if notional <= k), sizes[-1] if sizes else 500.0)
        v = pair.get(f"{key:g}", {}).get("pair_roundtrip_bps")
        if v is None:
            v = pair.get("500", {}).get("pair_roundtrip_bps")
        if v is None:
            return _GATE_DEFAULT_RT_BPS
        v = float(v)
        if key > 500.0:
            v500 = pair.get("500", {}).get("pair_roundtrip_bps")
            if v500 is not None:
                v = max(v, float(v500))
        return v
    except (KeyError, TypeError, ValueError):
        return _GATE_DEFAULT_RT_BPS


_BUCKETS = (("<2h", 0.0, 2.0), ("2-8h", 2.0, 8.0), ("8-24h", 8.0, 24.0), (">24h", 24.0, 1e9))


def _buckets(closes: list[dict[str, Any]],
             fees: dict[int, float] | None = None) -> dict[str, dict[str, Any]]:
    """Hold-class economics. With ``fees`` (id(trade) -> venue commission) the net is charged the
    actual fee bill; without it the net is the trade log's own fee-blind figure."""
    out: dict[str, dict[str, Any]] = {}
    for lbl, lo, hi in _BUCKETS:
        g = [x for x in closes if lo <= float(x.get("held_hours") or 0) < hi]
        nt = sum(float(x.get("notional") or 0) for x in g)
        net = sum(float(x.get("net") or 0) for x in g)
        row = {"n": len(g), "notional": round(nt, 2)}
        if fees is not None:
            fee = sum(fees.get(id(x), 0.0) for x in g)
            net -= fee
            row["fee"] = round(fee, 2)
        row["net"] = round(net, 2)
        row["bps"] = round(1e4 * net / nt, 2) if nt else 0.0
        out[lbl] = row
    return out


def _ms(stamp: Any) -> int | None:
    try:
        return int(datetime.fromisoformat(str(stamp)).timestamp() * 1000)
    except Exception:
        return None


def _fee_attribution(closes: list[dict[str, Any]], since_ms: int) -> dict[str, Any]:
    """Charge each logged round-trip the commission the VENUE actually billed for it.

    ORIGIN (2026-07-28). Every economic verdict this organ produces was computed from the trade
    log's ``net`` = price_pnl + est_funding. Neither term contains a fee: ``_tca`` records
    slippage-vs-mid only. So the hold-class verdicts, the symbol blacklist, and the forward track
    record that Gate 0 will size REAL capital on all omitted the dominant cost of the trade -- and
    this organ's own comment already called fees "the primary unit-economics lever". Disclosed and
    not gated is an open defect, so the gate is built here.

    The join is (symbol, open<=event<=close). The book holds at most one carry per symbol at a
    time, so those windows never overlap and each event is claimed by at most ONE trade; whatever
    is left over is UNATTRIBUTED -- commission the venue charged against no round-trip this book
    believes it made. That residual is the churn-loop fingerprint measured directly (the loop
    billed $1,746.66 against ~$126 of logged round-trips), so it is reported rather than spread
    silently over the trades that happen to be nearby.

    FUTURES COMMISSION ONLY -- /fapi income cannot see spot-leg fees, so this is a LOWER BOUND on
    the true bill and is labelled as one. A venue that cannot be read yields no fee-adjusted
    verdict at all: an unmeasured cost reported as zero is the phantom this whole organ exists to
    prevent.
    """
    try:
        from libs.execution import binance_testnet as _fut
        events = _fut.commission_events(since_ms)
    except Exception as e:                       # venue unreachable is not a fee defect
        return {"error": f"{type(e).__name__}: {e}",
                "note": "venue unreachable -- no fee-adjusted verdict this run"}

    spans: dict[str, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for x in closes:
        o, c = _ms(x.get("opened")), _ms(x.get("closed"))
        if o is not None and c is not None:
            spans[str(x.get("symbol"))].append((o, c, x))
    for v in spans.values():
        v.sort(key=lambda r: r[0])

    fees: dict[int, float] = {}
    attributed = unattributed = 0.0
    for ev in events:
        amt = float(ev["commission"])
        for o, c, tr in spans.get(ev["symbol"], ()):
            if o <= ev["time"] <= c:
                fees[id(tr)] = fees.get(id(tr), 0.0) + amt
                attributed += amt
                break
        else:
            unattributed += amt

    venue_total = attributed + unattributed
    logged_nt = sum(float(x.get("notional") or 0) for x in closes)
    return {
        "_fees": fees,                                    # popped before publish (id-keyed)
        "venue_commission": round(venue_total, 2),
        "attributed": round(attributed, 2),
        "unattributed": round(unattributed, 2),
        "unattributed_share": round(unattributed / venue_total, 3) if venue_total else None,
        "n_events": len(events),
        "fee_bps_of_logged_notional": (round(1e4 * venue_total / logged_nt, 2)
                                       if logged_nt else None),
        "scope": "futures commission only (/fapi income); spot-leg fees not visible -> LOWER BOUND",
    }


def _leg_share(trades: list[dict[str, Any]], key: str) -> float | None:
    """Maker share of one leg. None when no record carries a measurable mode for it.

    Legs that placed no order (`already-flat`) are excluded from the denominator -- see the R0064
    note at the `maker` block below; `libs.execution.leg_modes` owns the vocabulary for both this
    organ and scripts/fill_quality_monitor.
    """
    modes = [x[key] for x in trades if leg_modes.placed_order(x.get(key))]
    return round(sum(leg_modes.is_maker(m) for m in modes) / len(modes), 3) if modes else None


def _tape_sync(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Mirror the rolling buffer into the permanent execution tape, and report the margin.

    The buffer is capped at 500 events (run_cashcarry_executor._log_trade). At the observed event
    rate that is ~18.6 days of tape against this script's 14-day window -- only ~4.6 days of
    headroom before the buffer starts silently eating the window it is asked to analyse. Backfill
    is idempotent, so running it here makes the tape self-heal daily even when the executor is on
    an older build; the margin is surfaced so the squeeze can never arrive unannounced.
    """
    try:
        from libs.execution import execution_tape
        added = execution_tape.backfill(trades)
        cov = execution_tape.coverage()
        stamps = sorted(str(x.get("closed") or x.get("opened") or "") for x in trades if x)
        buf_days = 0.0
        if len(stamps) >= 2 and stamps[0] and stamps[-1]:
            buf_days = (datetime.fromisoformat(stamps[-1])
                        - datetime.fromisoformat(stamps[0])).total_seconds() / 86400
        return {"taped": cov["n"], "tape_days": cov["days"], "backfilled": added,
                "buffer_days": round(buf_days, 2),
                "window_margin_days": round(buf_days - _WINDOW_D, 2),
                "buffer_squeezing_window": bool(buf_days and buf_days < _WINDOW_D)}
    except Exception as e:  # observer -- never break the daily forensics run
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> None:
    trades = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
    tape = _tape_sync(trades)
    all_closes = [x for x in trades
                  if x.get("event") == "close" and x.get("held_hours") is not None]
    cutoff = (datetime.now(tz=UTC) - timedelta(days=_WINDOW_D)).isoformat()
    closes = [x for x in all_closes if str(x.get("closed", "")) >= cutoff]
    flags: list[str] = []

    hold = _buckets(closes)
    for lbl, b in hold.items():
        if b["n"] >= _MIN_N and b["bps"] < _BLEED_BPS:
            flags.append(f"hold-class {lbl} bleeding: {b['bps']} bps over {b['n']} trades "
                         f"(net ${b['net']})")

    # VENUE-TRUTH COST (2026-07-28). Everything above this line is fee-blind; everything below
    # charges the bill the exchange actually sent. Both are published because the DIVERGENCE is
    # the diagnostic -- replacing one number with the other would hide the measurement gap that
    # let a $1,750 fee fire read as a break-even book.
    since_ms = int((datetime.now(tz=UTC) - timedelta(days=_WINDOW_D)).timestamp() * 1000)
    fee_attr = _fee_attribution(closes, since_ms)
    fees = fee_attr.pop("_fees", None)
    hold_nof: dict[str, dict[str, Any]] | None = None
    if fees is not None:
        hold_nof = _buckets(closes, fees)
        for lbl, b in hold_nof.items():
            if b["n"] < _MIN_N or not b["notional"]:
                continue
            if b["bps"] < _BLEED_BPS <= hold[lbl]["bps"]:
                flags.append(f"hold-class {lbl} is NET-OF-FEE NEGATIVE ({b['bps']} bps, fee "
                             f"${b['fee']}) while its fee-blind net reads {hold[lbl]['bps']} bps "
                             "-- the logged verdict was an artifact of not charging the trade")
            # FEE INTENSITY is the execution-integrity measure, and it generalises past the churn
            # loop: a carry round-trip bills the futures leg twice (~5 bps taker each), so a class
            # paying many multiples of that is being charged for fills the book never intended,
            # whatever the mechanism. A sign test alone misses this -- the 07-28 fire landed on a
            # class ALREADY flagged bleeding, so it moved -42 -> -635 bps in silence.
            fbps = 1e4 * b["fee"] / b["notional"]
            if fbps > _FEE_BPS_MAX:
                flags.append(f"FEE INTENSITY hold-class {lbl}: ${b['fee']} on ${b['notional']:.0f} "
                             f"= {fbps:.0f} bps, {fbps / _FEE_RT_BPS:.0f}x the ~{_FEE_RT_BPS:.0f} "
                             "bps a futures round-trip should bill -- the venue is charging for "
                             "fills this book did not intend (churn-loop fingerprint; see "
                             "max_audit check_close_retry_loop)")
        share = fee_attr.get("unattributed_share")
        if share is not None and share > 0.25 and fee_attr["venue_commission"] > 25.0:
            flags.append(f"UNATTRIBUTED COMMISSION {fee_attr['unattributed']} of "
                         f"{fee_attr['venue_commission']} ({share:.0%}) matches no logged "
                         "round-trip -- the venue is billing against no position this book "
                         "believes it opened")

    # funding-at-open: the class that ate ~80% of gross profit pre-gate
    base = [x for x in closes if abs(float(x.get("funding_rate") or 0) - _BASELINE) < 1e-9]
    bn = sum(float(x.get("net") or 0) for x in base)
    bnot = sum(float(x.get("notional") or 0) for x in base)
    # entry-gate regression check, R0057 contract: a post-gate open is a regression iff its
    # funding could NOT beat the symbol's modelled round-trip over the minimum hold. Baseline
    # funding on a tight measured major legitimately passes; baseline funding on an unmeasured
    # or expensive book cannot.
    try:
        _cost_model = json.loads(_COST_MODEL.read_text("utf-8")) if _COST_MODEL.exists() else {}
    except (OSError, json.JSONDecodeError):
        _cost_model = {}
    # Same rolling window as every other flag in this file: the question is "is the gate
    # filtering NOW", and judging pre-R0057 opens against today's contract and today's cost
    # model is anachronistic on both axes (the 7 opens of 07-26/27 passed the gate as it stood
    # then). Within 14d, model-at-read ~= model-at-open; the exact close is the executor
    # stamping its gate arithmetic on the open row (rowed, behind the executor-lineage merge).
    _gate_cutoff = max(_GATE_DATE, cutoff)
    post_gate_base = []
    n_gate_window_opens = 0
    for x in trades:
        if x.get("event") != "open" or str(x.get("opened", "")) <= _gate_cutoff:
            continue
        n_gate_window_opens += 1
        f_open = float(x.get("funding_rate") or 0)
        rt = _gate_rt_bps(str(x.get("symbol")), float(x.get("notional") or 500.0), _cost_model)
        if f_open * 1e4 * _GATE_PERIODS <= rt:
            post_gate_base.append(x)
    if post_gate_base:
        flags.append(f"ENTRY-GATE REGRESSION: {len(post_gate_base)} open(s) whose funding could "
                     f"not beat the symbol's modelled round-trip over the minimum hold "
                     f"(R0057 per-symbol contract) -- gate is not filtering")

    per_sym: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for x in closes:
        s = str(x.get("symbol"))
        per_sym[s][0] += 1
        per_sym[s][1] += float(x.get("net") or 0)
        per_sym[s][2] += float(x.get("notional") or 0)
    worst = sorted(((s, n, net, 1e4 * net / nt if nt else 0.0)
                    for s, (n, net, nt) in per_sym.items() if n >= 5),
                   key=lambda r: r[2])[:5]
    for s, n, net, bps in worst:
        if net < -25.0 and bps < -20.0:
            flags.append(f"symbol {s} structurally bleeding: ${net:.0f} over {n} trades "
                         f"({bps:.0f} bps)")

    # THE DENYLIST'S EVIDENCE -- ALL-TIME, never windowed. Same bar as the executor's fence
    # (n >= 5 closes, realised <= -20 bps), computed over the FULL closed-trade record.
    #
    # WHY THIS KEY EXISTS SEPARATELY FROM `worst_symbols`: that list is 14d-ROLLING, which is
    # correct for the pager (an all-history flag re-pages forever after the fix works) and
    # exactly wrong for a fence. A symbol that PROVED it loses money does not stop having proved
    # it because a fortnight passed, so a windowed denylist rehabilitates every proven loser on a
    # fortnightly cycle and the desk re-buys the lesson it already paid for.
    #
    # RESTORED 2026-08-13 (R0158 sibling). This split shipped 2026-08-05 in a0026d98 and was
    # REVERTED by merge 8b981a50, which kept tests/execution/test_carry_entry_gate.py -- the file
    # asserting the fence reads this key -- while dropping the producer and reader that made it
    # true. The tests went red and stayed red, so the merge-union defect was visible the whole
    # time and read as an ordinary red suite. Measured at restoration: the rolling window held
    # 4 of 253 all-time closes and named ZERO bleeders, while SIX qualified all-time -- NOMUSDT
    # (-149.4 bps, the 2026-07-13 dead-man symbol), COMPUSDT (-106.4), ONEUSDT (-92.4),
    # 1000CATUSDT (-74.6), BNBUSDT (-65.8) and PEOPLEUSDT (-62.4). The book is paused on a
    # drawdown, which is WHY the window is nearly empty: the fence protects nothing at exactly
    # the moment a re-arm would re-open the names that caused the pause.
    #
    # The path back is a RE-MEASUREMENT that moves the all-time verdict, never the calendar.
    all_sym: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for x in all_closes:
        s = str(x.get("symbol"))
        all_sym[s][0] += 1
        all_sym[s][1] += float(x.get("net") or 0)
        all_sym[s][2] += float(x.get("notional") or 0)
    bleeding: list[dict[str, Any]] = sorted(
        ({"symbol": s, "n": int(n), "net": round(net, 2),
          "bps": round(1e4 * net / nt, 1)}
         for s, (n, net, nt) in all_sym.items()
         if n >= _DENY_MIN_N and nt and 1e4 * net / nt <= _DENY_BPS),
        key=lambda r: float(r["bps"]))   # worst first, so a reader sees the sharpest evidence

    # MAKER FILL-RATE ON THE PRIMARY BOOK (2026-07-26). The patient-maker opens shipped 07-24 to
    # cut a fee bill running ~2.5x the funding harvest, and the desk carried a standing duty to
    # "re-measure weekly until >60%" -- with NO instrument: _execute_pair returned the fill mode
    # and _log_trade threw it away, and the only `maker_share` in the repo belongs to a different
    # organ (run_crypto_testnet) whose web/binance.json last updated 2026-06-28. A fix whose effect
    # cannot be measured is a fix on trust. Legs are counted independently: a pair can rest maker
    # on spot and cross taker on futures, and that asymmetry is exactly the cost detail we need.
    #
    # R0064 (2026-08-05): the denominator used to be EVERY truthy mode string, which swept in
    # `already-flat` -- the mode `_close_goal_state` writes when the venue says the leg is already
    # flat. No order was placed and no fill happened, so such a leg cannot be maker; counting it
    # scored it non-maker and pushed `maker_share` under the 0.60 target on arithmetic alone. That
    # is a FALSE INTEGRITY FLAG: the desk gets paged about maker conversion by legs that never
    # traded. The vocabulary now lives in `libs.execution.leg_modes`, shared with
    # scripts/fill_quality_monitor so both organs measure the same tape the same way (R0324).
    # Exclusion is limited to the no-order markers: every mode that DID place an order still counts
    # against the target, so this can only remove phantom legs, never soften the bar.
    legs = [m for x in trades for m in (x.get("spot_mode"), x.get("fut_mode"))
            if leg_modes.placed_order(m)]
    maker = {
        "n_legs": len(legs),
        "maker_share": (round(sum(leg_modes.is_maker(m) for m in legs) / len(legs), 3)
                        if legs else None),
        "spot": _leg_share(trades, "spot_mode"),
        "fut": _leg_share(trades, "fut_mode"),
        "target": 0.60,
        "note": ("instrumented 2026-07-26; records written before that carry no mode, so n_legs "
                 "climbs from 0 as new fills land -- a null share is thin data, not a regression. "
                 "n_legs counts only legs that PLACED AN ORDER: no-order legs "
                 f"{sorted(leg_modes.NO_ORDER_MODES)} are excluded from the denominator (R0064)"),
    }
    # Narrowed out of the heterogeneous dict before comparing: `maker` holds str values too, so
    # mypy reads these operands as `str | float | None` and rejects the ordering comparisons.
    _share, _legs = maker["maker_share"], maker["n_legs"]
    if isinstance(_share, float) and isinstance(_legs, int) and _legs >= 20 and _share < 0.60:
        flags.append(f"maker fill-rate {_share:.1%} below the 60% target over "
                     f"{_legs} legs -- patient-maker opens are not converting; fees are "
                     "the dominant carry cost, so this is the primary unit-economics lever")

    if tape.get("buffer_squeezing_window"):
        flags.append(f"trade-log buffer holds {tape['buffer_days']}d < the {_WINDOW_D}d forensics "
                     "window -- this analysis is now silently losing its own tail; the permanent "
                     "tape (data/moat/execution_tape/) has the full history, read from there")

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_closes": len(closes),
        "hold_buckets": hold,
        # fee-blind (above) vs venue-truth (below) -- see _fee_attribution
        "hold_buckets_net_of_fees": hold_nof,
        "fee_attribution": fee_attr,
        "baseline_funding_class": {"n": len(base), "net": round(bn, 2),
                                   "bps": round(1e4 * bn / bnot, 2) if bnot else 0.0},
        # numerator AND denominator (L1.57): 0 violations over 0 window opens is "no evidence"
        # (paused book), not "gate healthy" -- readers must be able to tell them apart
        "post_gate_baseline_opens": len(post_gate_base),
        "post_gate_opens_examined": n_gate_window_opens,
        "maker_fill": maker,
        "execution_tape": tape,
        "worst_symbols": [{"symbol": s, "n": n, "net": round(net, 2), "bps": round(bps, 1)}
                          for s, n, net, bps in worst],
        "bleeding_symbols": bleeding,
        "bleeding_basis": {"window": "all-time", "n_closes": len(all_closes),
                           "min_n": _DENY_MIN_N, "bleed_bps": _DENY_BPS,
                           "note": "the executor's structural-bleed denylist reads THIS key; "
                                   "worst_symbols is 14d-rolling and is for alerts only"},
        "flags": flags,
        "origin": "recursion rule 2026-07-22: mechanization of the principal-supplied probes "
                  "that found gaps #42/#43/#34",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1), "utf-8")
    # same doc plus a "written" stamp: a checkout must be able to cite WHEN the evidence was
    # captured, not merely that it exists.
    #
    # ONLY FROM THE HOST THAT HOLDS THE TRADES (GAP 113). `data/cashcarry_trades.json` is
    # gitignored, so on any other box this analysis runs over nothing and produces a perfectly
    # well-formed document reporting `n_closes: 0` with every net at zero -- then commits it over
    # the real one. Measured 2026-08-13: a `pytest` run did exactly that, replacing 27 closes with
    # zero. That is WS-005 written into a TRACKED artifact by merely observing the system, and it
    # is undetectable afterwards: an empty forensics doc and a desk that closed nothing are the
    # same bytes.
    #
    # The untracked `_OUT` above is written unconditionally and deliberately -- it is this host's
    # own runtime state, the executor's denylist reads it, and a stale denylist is the dangerous
    # direction. What is guarded is only the shared, committed copy.
    owns, why = is_owning_host()
    if owns:
        _TRACKED.parent.mkdir(parents=True, exist_ok=True)
        _TRACKED.write_text(
            json.dumps({**out, "written": datetime.now(tz=UTC).isoformat()}, indent=1), "utf-8")
    else:
        print(f"trade forensics: tracked copy NOT written -- {why}")
    print(f"trade forensics: {len(closes)} closes | flags: {len(flags)}")
    for fl in flags:
        print("  !", fl)


if __name__ == "__main__":
    main()
