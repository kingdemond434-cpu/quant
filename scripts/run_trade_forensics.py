"""Daily trade-class forensics -- the mechanical version of the probes that found gaps #42/#43/#34.

On 2026-07-22 the principal's manual pushing surfaced three profit leaks the cycle had missed:
churn drag (-8.1%/yr in sub-8h holds), baseline-funding entries (-92.7 bps, ~80% of gross profit),
and concentrated leg-thrash losses. All three were visible in ONE artifact the desk already owned
-- data/cashcarry_trades.json -- bucketed three ways. Per the RECURSION RULE, that analysis is now
a standing daily check: pure python, quota-free, runs even when the brain is auth-dead (as it was
the day this was written). Writes web/trade_forensics.json; run_alerts pages on any bleeding class.

    python scripts/run_trade_forensics.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_TRADES = Path("data/cashcarry_trades.json")
_OUT = Path("web/trade_forensics.json")
_MIN_N = 15            # a class needs this many trades before its verdict is trusted
_WINDOW_D = 14.0       # ROLLING window: all-history flags would re-page forever even
                       # after fixes work; the question is "is it bleeding NOW"
_BLEED_BPS = -1.0      # class net worse than this (bps of notional) = defect
_FEE_RT_BPS = 10.0     # futures leg billed twice per round-trip at ~5 bps taker rack rate
_FEE_BPS_MAX = 50.0    # 5x that -- generous for maker/taker mix + partials, so anything above
                       # is fills the book never intended, not an execution-quality gradient
_BASELINE = 0.000100   # Binance default funding -- entry gate should keep these at zero
# entry-gate ship time -- any open at baseline funding AFTER this is a gate regression
_GATE_DATE = "2026-07-22T20:00:00+00:00"


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
    """Maker share of one leg. None when no record carries the field yet (pre-instrumentation)."""
    modes = [x[key] for x in trades if x.get(key)]
    return round(sum(m == "maker" for m in modes) / len(modes), 3) if modes else None


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
    closes = [x for x in trades if x.get("event") == "close" and x.get("held_hours") is not None]
    cutoff = (datetime.now(tz=UTC) - timedelta(days=_WINDOW_D)).isoformat()
    closes = [x for x in closes if str(x.get("closed", "")) >= cutoff]
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
    # entry-gate regression check: NEW opens at the exchange-default rate after the gate shipped
    post_gate_base = [x for x in trades
                      if x.get("event") == "open"
                      and str(x.get("opened", "")) > _GATE_DATE
                      and abs(float(x.get("funding_rate") or 0) - _BASELINE) < 1e-9]
    if post_gate_base:
        flags.append(f"ENTRY-GATE REGRESSION: {len(post_gate_base)} open(s) at baseline funding "
                     f"{_BASELINE} AFTER the gate shipped -- gate is not filtering")

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

    # MAKER FILL-RATE ON THE PRIMARY BOOK (2026-07-26). The patient-maker opens shipped 07-24 to
    # cut a fee bill running ~2.5x the funding harvest, and the desk carried a standing duty to
    # "re-measure weekly until >60%" -- with NO instrument: _execute_pair returned the fill mode
    # and _log_trade threw it away, and the only `maker_share` in the repo belongs to a different
    # organ (run_crypto_testnet) whose web/binance.json last updated 2026-06-28. A fix whose effect
    # cannot be measured is a fix on trust. Legs are counted independently: a pair can rest maker
    # on spot and cross taker on futures, and that asymmetry is exactly the cost detail we need.
    legs = [m for x in trades for m in (x.get("spot_mode"), x.get("fut_mode")) if m]
    maker = {
        "n_legs": len(legs),
        "maker_share": round(sum(m == "maker" for m in legs) / len(legs), 3) if legs else None,
        "spot": _leg_share(trades, "spot_mode"),
        "fut": _leg_share(trades, "fut_mode"),
        "target": 0.60,
        "note": ("instrumented 2026-07-26; records written before that carry no mode, so n_legs "
                 "climbs from 0 as new fills land -- a null share is thin data, not a regression"),
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
        "post_gate_baseline_opens": len(post_gate_base),
        "maker_fill": maker,
        "execution_tape": tape,
        "worst_symbols": [{"symbol": s, "n": n, "net": round(net, 2), "bps": round(bps, 1)}
                          for s, n, net, bps in worst],
        "flags": flags,
        "origin": "recursion rule 2026-07-22: mechanization of the principal-supplied probes "
                  "that found gaps #42/#43/#34",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1), "utf-8")
    print(f"trade forensics: {len(closes)} closes | flags: {len(flags)}")
    for fl in flags:
        print("  !", fl)


if __name__ == "__main__":
    main()
