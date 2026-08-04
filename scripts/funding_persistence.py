"""FUNDING PERSISTENCE -- does the desk's ENTRY SIGNAL predict what it is trying to HARVEST?

THE MOST DIAGNOSTIC UNTESTED QUESTION ON THE DESK. The carry executor selects symbols by CURRENT
funding rate, then the churn guard holds them >=24h. But funding pays every 8h, so what is
actually earned is funding over the HOLDING PERIOD -- not funding at entry. Nobody has ever
checked that those are related.

If funding mean-reverts fast, the desk systematically buys the spike and collects the reversion.
That would directly explain the hurdle report: $113 harvested against $876 of cost, i.e. the
harvest is a fraction of what the entry signal advertised.

THREE TESTS, cross-sectional across the liquid perp universe:
  1. PERSISTENCE   -- rank-correlation between funding at t and MEAN funding over t+1..t+3 (24h)
                      and t+1..t+9 (72h). This is the executor's actual assumption, stated.
  2. DECILE DECAY  -- take the TOP-funding decile at t (what the executor buys) and measure what
                      that basket actually pays over the next 24h/72h vs the universe median.
                      This is the realistic version: the executor does not buy the average symbol.
  3. HALF-LIFE     -- AR(1) on the funding series; how fast does an entry-time edge decay.

Free Binance funding history, same venue, same clock, no cross-source alignment -> the artifact
class that killed mSOL/CME/bithumb today is structurally impossible here.

Stage-A, zero promotion authority. Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/funding_persistence.json")
N_HIST = 500  # funding ticks per symbol (8h each -> ~166 days)


def _get(u, t=30):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def universe(n: int = 40) -> list[str]:
    """Liquid USDT perps by 24h quote volume -- the pool the executor actually picks from."""
    d = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    rows = [
        (float(x.get("quoteVolume", 0)), x["symbol"]) for x in d if x["symbol"].endswith("USDT")
    ]
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]


def funding(sym: str) -> list[tuple[int, float]]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={N_HIST}")
        return [(int(x["fundingTime"]) // 3600000, float(x["fundingRate"])) for x in d]
    except Exception:
        return []


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1]) if ra.std() and rb.std() else 0.0


def main() -> None:
    syms = universe()
    print(f"=== FUNDING PERSISTENCE | {len(syms)} liquid perps ===")
    print("    does funding at ENTRY predict funding over the HOLD? (the executor assumes yes)\n")
    series = {}
    for s in syms:
        f = funding(s)
        if len(f) >= 200:
            series[s] = dict(f)
    if len(series) < 15:
        print(f"  only {len(series)} usable symbols")
        return
    grid = sorted(set.intersection(*[set(v) for v in series.values()]))
    print(
        f"  {len(series)} symbols, {len(grid)} aligned funding periods "
        f"(~{len(grid) / 3:.0f} days)\n"
    )

    ics = {24: [], 72: []}
    dec = {24: [], 72: []}
    med = {24: [], 72: []}
    for i, t in enumerate(grid):
        cur = np.array([series[s][t] for s in series])
        for hrs, k in ((24, 3), (72, 9)):
            if i + k >= len(grid):
                continue
            fwd = np.array(
                [np.mean([series[s][grid[i + j]] for j in range(1, k + 1)]) for s in series]
            )
            ics[hrs].append(spearman(cur, fwd))
            top = np.argsort(cur)[-max(2, len(cur) // 10) :]  # what the executor buys
            dec[hrs].append(float(fwd[top].mean()))
            med[hrs].append(float(np.median(fwd)))

    res = {}
    for hrs in (24, 72):
        a = np.array(ics[hrs])
        t_ic = float(a.mean() / (a.std() / np.sqrt(len(a)))) if len(a) > 2 and a.std() else 0.0
        d, m = np.array(dec[hrs]), np.array(med[hrs])
        # annualise: funding pays 3x/day
        top_ann = float(d.mean() * 3 * 365 * 100)
        med_ann = float(m.mean() * 3 * 365 * 100)
        print(f"  --- {hrs}h holding period ---")
        print(
            f"    persistence IC (entry funding -> realised funding)  {a.mean():+.4f} "
            f"(t {t_ic:+.1f}, n={len(a)})"
        )
        print(f"    TOP-decile basket realises {top_ann:+7.2f}%/yr")
        print(f"    universe median realises   {med_ann:+7.2f}%/yr")
        print(f"    selection edge             {top_ann - med_ann:+7.2f}%/yr\n")
        res[f"{hrs}h"] = {
            "persistence_ic": round(float(a.mean()), 4),
            "ic_t": round(t_ic, 2),
            "top_decile_ann_pct": round(top_ann, 3),
            "median_ann_pct": round(med_ann, 3),
            "selection_edge_pct": round(top_ann - med_ann, 3),
        }

    # half-life of a funding shock
    hl = []
    for s in series:
        v = np.array([series[s][t] for t in grid])
        x0, x1 = v[:-1] - v.mean(), v[1:] - v.mean()
        b = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
        if 0 < abs(b) < 1:
            hl.append(-np.log(2) / np.log(abs(b)))
    if hl:
        h = float(np.median(hl))
        print(f"  funding shock half-life: {h:.1f} periods ({h * 8:.0f}h)")
        res["half_life_periods"] = round(h, 2)
        res["half_life_hours"] = round(h * 8, 1)

    e24 = res["24h"]["selection_edge_pct"]
    verdict = (
        "ENTRY SIGNAL WORKS -- top-decile selection beats the median materially"
        if e24 > 5
        else "ENTRY SIGNAL WEAK -- selection adds little over buying the median symbol"
        if e24 > 1
        else "ENTRY SIGNAL BROKEN -- selecting on current funding earns ~nothing extra"
    )
    print(f"\n  VERDICT: {verdict}")
    print("  This is the executor's core assumption, tested for the first time.")
    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "symbols": len(series),
                "periods": len(grid),
                "results": res,
                "verdict": verdict,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
