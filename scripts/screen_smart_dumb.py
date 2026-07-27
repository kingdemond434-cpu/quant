"""ELITE-TRADER INTELLIGENCE -- the falsifiable KERNEL of the 26-layer spec.

The spec's premise: skilled traders carry extractable predictive information. Rather than build
26 subsystems on an unproven premise, this tests the premise itself with the cheapest decisive
experiment the desk can run TODAY.

ANGLE-14: the desk ALREADY collects globalLongShortAccountRatio (ALL accounts = the RETAIL CROWD,
314 symbols/day) and already DSR-KILLED ls_contrarian on it. What it does NOT have is Binance's
TOP-TRADER positioning -- topLongShortPositionRatio / topLongShortAccountRatio -- i.e. the
"elite" cohort. Probe confirms they genuinely diverge (retail 66.8% long vs top 55.1% long).

Three signals screened at 4h granularity (~83d):
  1. elite_pos      -- top-trader POSITION ratio (size-weighted elite conviction)
  2. elite_acct     -- top-trader ACCOUNT ratio (elite headcount)
  3. smart_dumb_div -- elite MINUS retail (the smart-money-vs-dumb-money divergence; the single
                      most direct test of "do skilled traders lead the crowd?")

Hardened harness (de-contam + SUSPECT-LOOKAHEAD rails). Stage-A only, zero promotion authority.
Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_F = "https://fapi.binance.com/futures/data"
_K = "https://fapi.binance.com/fapi/v1/klines"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
PERIOD, LIMIT = "4h", 500


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-elite/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ratio(endpoint: str, sym: str) -> dict[int, float]:
    d = _get(f"{_F}/{endpoint}?symbol={sym}&period={PERIOD}&limit={LIMIT}")
    return {int(x["timestamp"]): float(x["longAccount"]) for x in d} if isinstance(d, list) else {}


def _klines(sym: str) -> dict[int, float]:
    d = _get(f"{_K}?symbol={sym}&interval={PERIOD}&limit={LIMIT}")
    return {int(r[0]): float(r[4]) for r in d} if isinstance(d, list) else {}


def main() -> None:
    results, pooled = [], {}
    for sym in SYMS:
        try:
            elite_pos = _ratio("topLongShortPositionRatio", sym)
            elite_acc = _ratio("topLongShortAccountRatio", sym)
            retail = _ratio("globalLongShortAccountRatio", sym)
            px = _klines(sym)
        except Exception as e:  # noqa: BLE001
            print(f"{sym:9s} DATA-BLOCKED ({type(e).__name__})")
            continue
        ts = sorted(set(elite_pos) & set(elite_acc) & set(retail) & set(px))
        if len(ts) < 90:
            print(f"{sym:9s} thin ({len(ts)})")
            continue
        close = np.array([px[t] for t in ts])
        ret = np.zeros(len(close))
        ret[1:] = close[1:] / close[:-1] - 1.0
        sigs = {"elite_pos": np.array([elite_pos[t] for t in ts]),
                "elite_acct": np.array([elite_acc[t] for t in ts]),
                "smart_dumb_div": np.array([elite_pos[t] - retail[t] for t in ts]),
                "retail_baseline": np.array([retail[t] for t in ts])}
        for name, sig in sigs.items():
            r = stage_a_screen(sig, ret, name=f"{sym}:{name}", zwin=20)
            r["symbol"], r["signal"] = sym, name
            results.append(r)
            pooled.setdefault(name, []).append((r.get("ic", 0.0), r.get("sharpe_momentum", 0.0),
                                                r.get("sharpe_reversal", 0.0)))
        print(f"{sym:9s} n={len(ts)} | " + " | ".join(
            f"{k}: IC {next(x for x in results if x['symbol']==sym and x['signal']==k).get('ic'):+.3f}"
            for k in sigs))

    print("\n=== POOLED across symbols (the honest read: N = symbols, not observations) ===")
    for name, vals in pooled.items():
        ics = np.array([v[0] for v in vals]); mom = np.array([v[1] for v in vals])
        rev = np.array([v[2] for v in vals])
        t = float(ics.mean() / (ics.std() / np.sqrt(len(ics)))) if len(ics) > 1 and ics.std() else 0.0
        print(f"  {name:18s} mean IC {ics.mean():+.4f} (t {t:+.2f}, n={len(ics)}) | "
              f"mean momSh {mom.mean():+.2f} | mean revSh {rev.mean():+.2f}")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nper-symbol SCREEN-INTERESTING: {len(surv)}/{len(results)} -> {surv[:8]}")
    Path("data/elite_trader_screen.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "period": PERIOD,
         "results": results}, indent=1), "utf-8")


if __name__ == "__main__":
    main()
