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
from datetime import UTC, datetime
from pathlib import Path

_TRADES = Path("data/cashcarry_trades.json")
_OUT = Path("web/trade_forensics.json")
_MIN_N = 15            # a class needs this many trades before its verdict is trusted
_BLEED_BPS = -1.0      # class net worse than this (bps of notional) = defect
_BASELINE = 0.000100   # Binance default funding -- entry gate should keep these at zero
# entry-gate ship time -- any open at baseline funding AFTER this is a gate regression
_GATE_DATE = "2026-07-22T20:00:00+00:00"


def _buckets(closes: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for lbl, lo, hi in (("<2h", 0.0, 2.0), ("2-8h", 2.0, 8.0),
                        ("8-24h", 8.0, 24.0), (">24h", 24.0, 1e9)):
        g = [x for x in closes if lo <= float(x.get("held_hours") or 0) < hi]
        nt = sum(float(x.get("notional") or 0) for x in g)
        net = sum(float(x.get("net") or 0) for x in g)
        out[lbl] = {"n": len(g), "notional": round(nt, 2), "net": round(net, 2),
                    "bps": round(1e4 * net / nt, 2) if nt else 0.0}
    return out


def main() -> None:
    trades = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
    closes = [x for x in trades if x.get("event") == "close" and x.get("held_hours") is not None]
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

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_closes": len(closes),
        "hold_buckets": hold,
        "baseline_funding_class": {"n": len(base), "net": round(bn, 2),
                                   "bps": round(1e4 * bn / bnot, 2) if bnot else 0.0},
        "post_gate_baseline_opens": len(post_gate_base),
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
