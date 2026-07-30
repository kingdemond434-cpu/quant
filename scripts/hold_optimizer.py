"""HOLD OPTIMIZER -- set _MIN_HOLD_H from REALISED closes, not from a simulated scan.

WHY THIS SUPERSEDES optimal_hold.py. That earlier scan produced "24h +5.80%/yr, 48h +13.97%/yr,
72h +16.97%/yr" and I quoted ~+11pp/yr as available. It was a MODELLED sweep. This reads the 249
actual closes the executor has logged, each with its realised held_hours, funding_rate, notional
and price_pnl (whose exit marks come from ACTUAL FILLS, so slippage on both legs is inside it).
Under the reality-feedback principle, realised closes outrank a sweep.

THE QUESTION THAT MUST BE ANSWERED FIRST -- and it is a measurement question, not a tuning one:
the desk's median realised hold is 14.9h while _MIN_HOLD_H is 24. Either the churn guard is being
escaped constantly, or most of those 249 closes PREDATE the guard. Those two worlds demand
opposite actions, and raising the parameter in the second world would change nothing at all while
appearing to fix something. So this splits the sample by era before it computes anything.

NET PER TRADE, from fields that actually exist:
    funding_earned = notional * funding_rate * (held_hours / 8)
    net            = funding_earned + price_pnl
price_pnl already contains entry AND exit slippage on both legs. It does NOT contain explicit
fees -- that field does not exist yet (see execution_bottleneck.py Q3), so every net below is an
UPPER BOUND on true profitability. Stated, not buried.

Read-only. Touches no orders and no config. Run from repo root.
"""
from __future__ import annotations

import itertools
import json
import statistics as st
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data/cashcarry_trades.json"
OUT = ROOT / "data/hold_optimizer.json"

# The churn guard (gap #42) landed with _MIN_HOLD_H. Closes before this date were not subject to
# any minimum hold, so pooling the two eras measures a policy that no longer exists.
GUARD_DATE = "2026-07-22"
BUCKETS = [(0, 8), (8, 16), (16, 24), (24, 36), (36, 48), (48, 72), (72, 1e9)]


def _load():
    t = json.loads(TRADES.read_text("utf-8"))
    rows = t if isinstance(t, list) else t.get("trades", [])
    out = []
    for r in rows:
        if r.get("event") != "close":
            continue
        h, n, f = r.get("held_hours"), r.get("notional"), r.get("funding_rate")
        pp = r.get("price_pnl")
        if None in (h, n, f, pp) or not n:
            continue
        h, n, f, pp = float(h), float(n), float(f), float(pp)
        if h <= 0 or n <= 0:
            continue
        fund = n * f * (h / 8.0)
        out.append({"sym": r.get("symbol"), "closed": (r.get("closed") or "")[:10],
                    "held_h": h, "notional": n, "funding_rate": f, "price_pnl": pp,
                    "funding_earned": fund, "net": fund + pp,
                    "net_bps": (fund + pp) / n * 1e4,
                    "apr_pct": ((fund + pp) / n) * (8760.0 / h) * 100.0})
    return out


def _summarise(rows, label):
    if not rows:
        print(f"  {label:<26} (no closes)")
        return None
    nets = [r["net_bps"] for r in rows]
    holds = [r["held_h"] for r in rows]
    sub24 = sum(1 for h in holds if h < 24) / len(holds) * 100
    print(f"  {label:<26} n={len(rows):<4} median hold {st.median(holds):>5.1f}h  "
          f"<24h: {sub24:>5.1f}%  median net {st.median(nets):+7.2f}bps")
    return {"label": label, "n": len(rows), "median_hold_h": round(st.median(holds), 2),
            "pct_under_24h": round(sub24, 1), "median_net_bps": round(st.median(nets), 3)}


def main() -> None:
    rows = _load()
    if len(rows) < 30:
        raise SystemExit(f"only {len(rows)} usable closes -- refusing to tune on this")
    print("=== HOLD OPTIMIZER -- realised closes, not a simulated sweep ===")
    print(f"    {len(rows)} closes carry held_hours + funding_rate + notional + price_pnl")
    print("    net = funding_earned + price_pnl; price_pnl includes slippage from ACTUAL fills")
    print("    FEES ARE NOT IN THIS DATA -> every net below is an UPPER BOUND\n")

    # ---------------------------------------------------------------- ERA SPLIT (do this first)
    print("ERA SPLIT -- was the 14.9h median a live problem or a dead policy?\n")
    pre = [r for r in rows if r["closed"] and r["closed"] < GUARD_DATE]
    post = [r for r in rows if r["closed"] and r["closed"] >= GUARD_DATE]
    eras = [_summarise(pre, f"PRE-guard (<{GUARD_DATE})"), _summarise(post, f"POST-guard (>={GUARD_DATE})")]
    eras = [e for e in eras if e]

    # COMPARE ERAS, do not test the post-era against an absolute threshold. v1 used
    # "pct_under_24h < 25" and declared the guard ESCAPED at 30% -- while the median hold had
    # gone 13.7h -> 42.2h and sub-24h closes had fallen 68.9% -> 30.0%. That is a guard working,
    # and the residual 30% is the rails and funding-panic escapes, which are SUPPOSED to fire.
    # An absolute cutoff on a quantity whose baseline moved is a wrong-measurement error.
    if len(eras) == 2 and eras[1]["n"] >= 20:
        improved = eras[0]["pct_under_24h"] - eras[1]["pct_under_24h"]
        print(f"\n  sub-24h closes: {eras[0]['pct_under_24h']:.1f}% -> "
              f"{eras[1]['pct_under_24h']:.1f}% ({improved:+.1f}pp); median hold "
              f"{eras[0]['median_hold_h']:.1f}h -> {eras[1]['median_hold_h']:.1f}h")
        if improved > 20:
            print("\n  VERDICT: the churn guard IS WORKING. The 14.9h pooled median is dominated")
            print("  by PRE-guard closes and describes a policy that no longer runs. My earlier")
            print("  claim that the desk's EFFECTIVE hold sits in the loss region was drawn from")
            print("  the pooled number and is WITHDRAWN. The residual sub-24h closes are the rail")
            print("  and funding-panic escapes, which are supposed to fire.")
        else:
            print("\n  VERDICT: the guard is being ESCAPED. Sub-24h closes persist at nearly the")
            print("  pre-guard rate, so the binding constraint is the escape path (rails /")
            print("  funding-panic), NOT _MIN_HOLD_H. Raising the constant would change nothing.")

    # ---------------------------------------------------------------- BUCKETS, POST-GUARD ONLY
    use = post if len(post) >= 40 else rows
    scope = "POST-guard only" if use is post else "ALL closes (post-guard sample too small)"
    print(f"\nNET BY REALISED HOLD -- {scope}, n={len(use)}\n")
    print(f"  {'bucket':<12}{'n':>5}{'med hold':>10}{'med net':>10}{'mean net':>10}"
          f"{'med APR':>10}  {'win%':>6}")
    out_b = []
    for lo, hi in BUCKETS:
        b = [r for r in use if lo <= r["held_h"] < hi]
        if not b:
            continue
        nets = [r["net_bps"] for r in b]
        aprs = [r["apr_pct"] for r in b]
        win = sum(1 for x in nets if x > 0) / len(b) * 100
        tag = f"{lo}-{'inf' if hi > 1e8 else int(hi)}h"
        flag = "  <-- n too small" if len(b) < 12 else ""
        print(f"  {tag:<12}{len(b):>5}{st.median([r['held_h'] for r in b]):>9.1f}h"
              f"{st.median(nets):>+10.2f}{st.mean(nets):>+10.2f}{st.median(aprs):>+9.1f}%"
              f"{win:>6.0f}%{flag}")
        out_b.append({"bucket": tag, "n": len(b), "median_net_bps": round(st.median(nets), 3),
                      "mean_net_bps": round(st.mean(nets), 3),
                      "median_apr_pct": round(st.median(aprs), 2), "win_pct": round(win, 1)})

    print("\n  APR ANNUALISES A SHORT HOLD, WHICH AMPLIFIES NOISE -- an 8h trade's APR is its bps")
    print("  times 1095. Median net bps is the honest per-trade number; APR is shown because the")
    print("  objective is E[log wealth] and capital recycling rate genuinely matters, but any")
    print("  bucket with n<12 is flagged and must not drive the setting.")

    ranked = [b for b in out_b if b["n"] >= 12]
    rec = max(ranked, key=lambda b: b["median_net_bps"]) if ranked else None
    print("\n=== RECOMMENDATION ===")
    if not rec:
        print("  NO BUCKET REACHES n>=12. There is not enough realised evidence to set the hold")
        print("  from data. Leaving _MIN_HOLD_H unchanged is the correct action: tuning a live")
        print("  money parameter on <12 observations per arm is exactly the overfitting this desk")
        print("  kills hypotheses for, and it would be indefensible under the doctrine adopted")
        print("  today. The unblocker is the TCA fields, not a better search over this sample.")
    else:
        print(f"  best-supported bucket: {rec['bucket']}  n={rec['n']}  "
              f"median net {rec['median_net_bps']:+.2f}bps  median APR {rec['median_apr_pct']:+.1f}%")
        # MONOTONICITY TEST -- the difference between a hold-time EFFECT and noise.
        signs = [1 if b["median_net_bps"] > 0 else -1 for b in ranked]
        flips = sum(1 for a, b in itertools.pairwise(signs) if a != b)
        print(f"  sign pattern across {len(ranked)} adequately-sampled buckets: "
              f"{''.join('+' if s > 0 else '-' for s in signs)}  ({flips} flips)")
        if flips >= 2:
            print("  NON-MONOTONIC WITH MULTIPLE SIGN FLIPS. A genuine hold-time effect is smooth")
            print("  over a region; alternating signs across adjacent buckets is a NOISE")
            print("  SIGNATURE. Median and mean also disagree on sign in several buckets, which")
            print("  means heavy tails and an unstable central estimate. This sample cannot")
            print("  identify an optimum, and fitting the single best bucket out of seven is")
            print("  max-order-statistic selection -- the winner's curse this desk kills")
            print("  hypotheses for. DO NOT MOVE THE PARAMETER ON THIS EVIDENCE.")
        pos = [b for b in ranked if b["median_net_bps"] > 0]
        if not pos:
            print("  BUT EVERY ADEQUATELY-SAMPLED BUCKET HAS NEGATIVE MEDIAN NET. No hold time")
            print("  makes this carry profitable on realised data -- and remember fees are NOT in")
            print("  these numbers, so the truth is worse. This is not a tuning problem. Changing")
            print("  _MIN_HOLD_H cannot fix a strategy whose realised net is negative at every")
            print("  horizon; the entry gate halting new opens is the correct response, and the")
            print("  real unblocker is measuring cost per symbol so the gate can pass on evidence.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n_closes": len(rows), "eras": eras, "scope": scope,
                               "buckets": out_b, "recommendation": rec,
                               "caveat": "fees absent from trade log -> all nets are upper bounds"},
                              indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
