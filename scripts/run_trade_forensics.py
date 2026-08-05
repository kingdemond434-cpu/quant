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
_BASELINE = 0.000100   # Binance default funding -- entry gate should keep these at zero
# entry-gate ship time -- any open at baseline funding AFTER this is a gate regression
_GATE_DATE = "2026-07-22T20:00:00+00:00"
# THE EXECUTOR'S OWN FUNDING FLOOR, mirrored (2026-08-05). The regression check below used to
# match funding EXACTLY at _BASELINE, so it saw the opens sitting ON the venue default and MISSED
# every open BELOW it -- BNBUSDT went on at 3.0e-05 (07-31) and 6.6e-05 (08-01), both further
# under the bar than the two it did report, and both invisible. A detector that under-counts the
# defect it exists to catch is worse than no detector: it reports "2" and reads as bounded.
# Mirrored rather than imported because importing the executor module opens venue connections;
# tests/test_carry_entry_gate.py asserts the two constants stay equal, so drift fails CI instead
# of silently re-blinding this check.
_MIN_FUNDING = 0.00015
# DENYLIST EVIDENCE IS ALL-TIME, ALERTS ARE ROLLING (2026-08-05). `worst_symbols` feeds two
# consumers with opposite time requirements: the pager (which must forget, or it re-pages forever)
# and the executor's structural-bleed denylist (which must NOT forget -- a symbol that PROVED it
# loses money does not stop having proved it because 14 days passed). They shared one 14d-rolling
# key, so the denylist quietly rehabilitated every proven loser on a fortnightly cycle and the
# desk re-opened it. Split: `worst_symbols` stays rolling for flags, `bleeding_symbols` is the
# all-time verdict the fence reads.
_DENY_BPS = -20.0      # all-time realised net bps at which a symbol is structurally bleeding
_DENY_MIN_N = 5        # minimum closed trades before that verdict is trusted


def _buckets(closes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for lbl, lo, hi in (("<2h", 0.0, 2.0), ("2-8h", 2.0, 8.0),
                        ("8-24h", 8.0, 24.0), (">24h", 24.0, 1e9)):
        g = [x for x in closes if lo <= float(x.get("held_hours") or 0) < hi]
        nt = sum(float(x.get("notional") or 0) for x in g)
        net = sum(float(x.get("net") or 0) for x in g)
        out[lbl] = {"n": len(g), "notional": round(nt, 2), "net": round(net, 2),
                    "bps": round(1e4 * net / nt, 2) if nt else 0.0}
    return out


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

    # funding-at-open: the class that ate ~80% of gross profit pre-gate
    base = [x for x in closes if abs(float(x.get("funding_rate") or 0) - _BASELINE) < 1e-9]
    bn = sum(float(x.get("net") or 0) for x in base)
    bnot = sum(float(x.get("notional") or 0) for x in base)
    # entry-gate regression check: NEW opens BELOW the executor's funding floor after the gate
    # shipped. Below-the-floor, not equal-to-baseline: the floor is what the gate actually
    # enforces, so anything under it is a bypass regardless of where it sits.
    post_gate_base = [x for x in trades
                      if x.get("event") == "open"
                      and str(x.get("opened", "")) > _GATE_DATE
                      and float(x.get("funding_rate") or 0) < _MIN_FUNDING]
    if post_gate_base:
        worst_rate = min(float(x.get("funding_rate") or 0) for x in post_gate_base)
        flags.append(f"ENTRY-GATE REGRESSION: {len(post_gate_base)} open(s) below the "
                     f"{_MIN_FUNDING} funding floor AFTER the gate shipped (worst {worst_rate:g}) "
                     "-- gate is not filtering")

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
    # WHY THIS EXISTS: `worst_symbols` above is 14d-rolling and today holds 42 of 253 all-time
    # closes, so it named ONE bleeder (1000CATUSDT) while six qualify all-time -- and the
    # executor's fence, reading that key, therefore let BNBUSDT (-65.8 bps over 13 closes, and
    # named as a proven loser in the executor's own source comment) back on 07-31 and 08-01.
    # An exclusion whose path back is the passage of TIME is not evidence-driven; the path back
    # here is a re-measurement that moves the all-time verdict, which is the only thing that
    # should ever lift it.
    all_sym: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for x in all_closes:
        s = str(x.get("symbol"))
        all_sym[s][0] += 1
        all_sym[s][1] += float(x.get("net") or 0)
        all_sym[s][2] += float(x.get("notional") or 0)
    bleeding = sorted(({"symbol": s, "n": int(n), "net": round(net, 2),
                        "bps": round(1e4 * net / nt, 1)}
                       for s, (n, net, nt) in all_sym.items()
                       if n >= _DENY_MIN_N and nt and 1e4 * net / nt <= _DENY_BPS),
                      key=lambda r: r["bps"])

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
    share, n_legs = maker["maker_share"], len(legs)
    if isinstance(share, float) and n_legs >= 20 and share < 0.60:
        flags.append(f"maker fill-rate {share:.1%} below the 60% target over "
                     f"{n_legs} legs -- patient-maker opens are not converting; fees are "
                     "the dominant carry cost, so this is the primary unit-economics lever")

    if tape.get("buffer_squeezing_window"):
        flags.append(f"trade-log buffer holds {tape['buffer_days']}d < the {_WINDOW_D}d forensics "
                     "window -- this analysis is now silently losing its own tail; the permanent "
                     "tape (data/moat/execution_tape/) has the full history, read from there")

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_closes": len(closes),
        "hold_buckets": hold,
        "baseline_funding_class": {"n": len(base), "net": round(bn, 2),
                                   "bps": round(1e4 * bn / bnot, 2) if bnot else 0.0},
        "post_gate_baseline_opens": len(post_gate_base),
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
    print(f"trade forensics: {len(closes)} closes | flags: {len(flags)}")
    for fl in flags:
        print("  !", fl)


if __name__ == "__main__":
    main()
