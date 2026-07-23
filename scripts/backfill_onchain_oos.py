#!/usr/bin/env python3
"""RECONSTRUCTED HELD-OUT OOS VALIDATION -- on-chain throughput axis (principal 2026-07-23,
MAX_SURVIVORS_PROGRAM Part 1 #1: collapse the 40-day clock with reconstructed history).

THE INTEGRITY PROBLEM this solves correctly: run_axis_shadows' forward clock derives its ENTIRE
statistical validity from the fact that its rows are dated AFTER pre-registration -- so they cannot
have been overfit. Backfilling reconstructed history straight into that clock would DESTROY that
basis (the collector's screen already SAW ~2y of history). So this does NOT touch the clock.

Instead it does the only statistically-honest form of the backfill:
  1. Pull FULL history (~15y) of on-chain throughput + BTC price from blockchain.info.
  2. DIFF-VERIFY the reconstruction against the forward-collected ground truth
     (data/onchain_activity.jsonl). If the reconstructed value for an overlap date does not match
     what the live collector recorded, the reconstruction is misaligned (timezone/label lookahead,
     the bithumb class) -> ABORT. This is the mandatory anti-phantom gate.
  3. LOCK the hypothesis params from the SCREEN window (the recent ~730d the collector fit on):
     z20 throughput, direction = -1 (reversal). No tuning here.
  4. BACKTEST those locked params on the HELD-OUT earlier history the screen never saw = a genuine
     out-of-sample test, available TODAY instead of in 40 forward days.
  5. Report full stats (IC, Sharpe, deflated Sharpe, sub-period regime split) to its OWN report
     file. Verdict is COMPLEMENTARY to the forward clock, never a replacement -- a real edge should
     survive BOTH. Zero promotion authority (two-stage law).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio

_THRU = ("https://api.blockchain.info/charts/estimated-transaction-volume-usd"
         "?timespan=all&format=json&sampled=false")
_PRICE = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"
_FWD = Path("data/onchain_activity.jsonl")
_OUT = Path("reports/reconstructed_oos/onchain_throughput.json")
_SCREEN_DAYS = 730           # the recent window the collector's screen fit on -> held out = older
_PRICE_FLOOR = 100.0         # ignore the pre-2013 near-zero-price regime (garbage returns)
_VERIFY_TOL = 0.02           # reconstructed vs forward ground-truth: <=2% or it is misaligned


def _chart(url: str) -> dict[str, float]:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-backfill"})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode())
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])}


def main() -> None:
    thru, price = _chart(_THRU), _chart(_PRICE)
    print(f"pulled: throughput {len(thru)} days, price {len(price)} days")

    # --- 1. DIFF-VERIFY reconstruction vs forward ground truth (anti-phantom gate) ------------
    verified = 0
    if _FWD.exists():
        for line in _FWD.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            d, live = row.get("date"), row.get("throughput_usd")
            if d in thru and live:
                rel = abs(thru[d] - float(live)) / abs(float(live))
                print(f"  diff-verify {d}: reconstructed {thru[d]:,.0f} vs live {float(live):,.0f} "
                      f"-> {rel*100:.3f}%")
                if rel > _VERIFY_TOL:
                    raise SystemExit(f"ABORT: reconstruction misaligned at {d} ({rel*100:.1f}%) "
                                     "-- timezone/label lookahead class; do NOT trust this OOS")
                verified += 1
    if verified == 0:
        print("  WARN: no overlap date to diff-verify yet (forward clock has too few rows) -- "
              "OOS is provisional until an overlap day confirms alignment")

    # --- 2. build aligned series, floor out the pre-liquid regime ------------------------------
    dates = sorted(d for d in (set(thru) & set(price)) if price[d] >= _PRICE_FLOOR)
    sig = np.array([thru[d] for d in dates])
    px = np.array([price[d] for d in dates])
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0

    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    # --- 3. split: recent SCREEN window (locked params) vs HELD-OUT older history -------------
    cutoff = (datetime.now(tz=UTC).date() - timedelta(days=_SCREEN_DAYS)).isoformat()
    held = [i for i, d in enumerate(dates) if d < cutoff and i >= 20]
    if len(held) < 200:
        raise SystemExit(f"only {len(held)} held-out days -- need >=200 for a meaningful OOS")

    # --- 4. backtest LOCKED params (z20, direction=-1 reversal) on the held-out OOS -----------
    direction = -1
    pos = np.sign(z) * direction
    strat = np.array([pos[i] * ret[i + 1] for i in held if i + 1 < len(ret)], dtype="float64")
    # honest IC: rank corr of signal[t] vs ret[t+1] over held-out
    hz = np.array([z[i] for i in held if i + 1 < len(ret)])
    hr = np.array([ret[i + 1] for i in held if i + 1 < len(ret)])
    ic = float(np.corrcoef(hz, hr)[0, 1]) if len(hz) > 2 and hz.std() > 0 else 0.0

    shp = sharpe_ratio(strat)
    ann = shp * np.sqrt(365)
    dsr = deflated_sharpe_ratio(strat, n_trials=6, sharpe_estimates=np.array([shp, -shp]))
    # regime split: thirds of the held-out window
    third = len(strat) // 3
    subs = [float(sharpe_ratio(strat[i * third:(i + 1) * third]) * np.sqrt(365))
            for i in range(3)] if third > 20 else []

    held_start, held_end = dates[held[0]], dates[held[-1]]
    verdict = ("OOS-SURVIVES" if (dsr.passed and ann > 0.5 and ic * direction < 0)
               else "OOS-FAILS")
    payload = {
        "axis": "onchain_activity_throughput",
        "generated": datetime.now(tz=UTC).isoformat(),
        "params_locked_from": f"recent {_SCREEN_DAYS}d screen window",
        "held_out_window": f"{held_start} .. {held_end}",
        "held_out_days": len(strat),
        "diff_verified_days": verified,
        "direction": direction,
        "ic_heldout": round(ic, 4),
        "ann_sharpe_heldout": round(ann, 3),
        "deflated_sharpe": round(float(dsr.dsr), 3),
        "dsr_passed": bool(dsr.passed),
        "regime_thirds_ann_sharpe": [round(s, 2) for s in subs],
        "cum_return_heldout": round(float(np.prod(1.0 + strat) - 1.0), 4),
        "verdict": verdict,
        "note": ("Reconstructed held-out OOS, params locked from the recent screen. COMPLEMENTARY "
                 "to the forward clock, NOT a replacement -- zero promotion authority. A real edge "
                 "survives both. Regime-split guards a signal that only worked one era."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n=== RECONSTRUCTED HELD-OUT OOS: onchain throughput ===")
    print(f"  held-out: {held_start}..{held_end} ({len(strat)} days), diff-verified {verified}d")
    print(f"  IC {ic:+.4f} | ann Sharpe {ann:+.3f} | deflated {float(dsr.dsr):+.3f} "
          f"(pass={dsr.passed})")
    print(f"  regime thirds (ann Sharpe): {[round(s,2) for s in subs]}")
    print(f"  VERDICT: {verdict}")
    print(f"  -> {_OUT}")


if __name__ == "__main__":
    main()
