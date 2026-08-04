"""INFORMATION FUSION ENGINE -- test whether WEAK signals combine into a usable one.

MOTIVATION IS EMPIRICAL, NOT THEORETICAL. This session's only replicated result came from a
COMBINED filter (profitable + Sharpe + consistency + drawdown: 62% in-sample, 60% out-of-sample)
while every single criterion alone gave nothing. The desk is full of weak singles that were each
killed alone and never tested together:
    stablecoin_supply IC 0.067 | dex_volume ~0.05 | protocol_fees ~0.06 | defi_tvl ~ -0.02
    kimchi premium IC 0.24 (KRW capital-control flow, orthogonal to all of the above)

MULTIPLICITY IS THE KILLER HERE: k signals give 2^k subsets, so testing "all combinations" is a
guaranteed false-positive factory. Discipline applied:
  1. PRE-REGISTERED combinations only -- each must have a stated economic reason, no subset sweep.
  2. Bonferroni across the number tested.
  3. Equal-weight z-composites ONLY -- no fitted weights (fitting weights on the same sample is
     how a fusion engine becomes an overfitting engine).
  4. Report the honest comparison: does the composite beat its BEST component? A composite that
     merely tracks its strongest member is not fusion, it is relabelling.

Stage-A, zero promotion authority. Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _get(u, t=40):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def binance():
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {
        datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
        for r in rows
    }


def stables():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    o = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            o[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return o


def llama_tvl():
    return {
        datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
        for x in _get("https://api.llama.fi/v2/historicalChainTvl")
    }


def llama_chart(u):
    return {
        datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
        for ts, v in _get(u).get("totalDataChart", [])
    }


def kimchi():
    kb = {
        str(r["candle_date_time_utc"])[:10]: float(r["trade_price"])
        for r in _get("https://api.upbit.com/v1/candles/days?market=KRW-BTC&count=200")
    }
    res = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=300d")[
        "chart"
    ]["result"][0]
    fx = {
        datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
        for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False)
        if c
    }
    return kb, fx


# PRE-REGISTERED combinations, each with an economic reason. NO subset sweep.
COMBOS = {
    "liquidity_expansion (M1 chain)": (
        ["stablecoin_supply", "defi_tvl"],
        "same mechanism node observed two ways: dollar liquidity entering the system",
    ),
    "onchain_economic_activity": (
        ["dex_volume", "protocol_fees"],
        "real usage/revenue -- two views of the same economic throughput",
    ),
    "liquidity_plus_activity": (
        ["stablecoin_supply", "dex_volume", "protocol_fees"],
        "capital arriving AND being used -- supply alone may be idle",
    ),
    "flow_plus_regional (orthogonal fuse)": (
        ["stablecoin_supply", "kimchi"],
        "global dollar liquidity + KRW capital-control flow: genuinely different mechanisms",
    ),
    "full_stack": (
        ["stablecoin_supply", "dex_volume", "protocol_fees", "kimchi"],
        "all surviving weak signals, equal weight",
    ),
}


def z(series: np.ndarray, w: int = 20) -> np.ndarray:
    o = np.zeros(len(series))
    for t in range(w, len(series)):
        win = series[t - w : t]
        sd = win.std()
        o[t] = (series[t] - win.mean()) / sd if sd > 0 else 0.0
    return o


def main() -> None:
    gb = binance()
    kb, fx = kimchi()
    raw = {
        "stablecoin_supply": stables(),
        "defi_tvl": llama_tvl(),
        "dex_volume": llama_chart(
            "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true"
        ),
        "protocol_fees": llama_chart(
            "https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true"
        ),
        "kimchi": {d: kb[d] / fx[d] / gb[d] - 1.0 for d in (set(kb) & set(fx) & set(gb))},
    }
    dates = sorted(set(gb).intersection(*[set(v) for v in raw.values()]))
    print(
        f"aligned dates across ALL components: {len(dates)} "
        f"(kimchi is the binding constraint at ~{len(raw['kimchi'])})"
    )
    if len(dates) < 80:
        print("insufficient overlap")
        return
    px = np.array([gb[d] for d in dates])
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0
    Z = {k: z(np.array([v[d] for d in dates])) for k, v in raw.items()}

    print("\n--- components alone (the baseline each combo must beat) ---")
    base = {}
    for k, zz in Z.items():
        r = stage_a_screen(zz, ret, name=k, zwin=20)
        ic = r.get("ic") or 0.0
        rs = r.get("sharpe_reversal") or 0.0
        base[k] = abs(ic)
        print(f"  {k:22s} IC {ic:+.4f}  revSh {rs:+.2f}  {r.get('verdict')}")

    n_tests = len(COMBOS)
    print(
        f"\n--- pre-registered fusions (Bonferroni alpha {0.05 / n_tests:.4f}, "
        f"equal-weight only, no fitted weights) ---"
    )
    out = []
    for name, (members, why) in COMBOS.items():
        comp = np.mean([Z[m] for m in members], axis=0)
        r = stage_a_screen(comp, ret, name=name, zwin=20)
        best_single = max(base[m] for m in members)
        cic = r.get("ic") or 0.0
        ic = abs(cic)
        lift = ic - best_single
        verdict = (
            "FUSION ADDS VALUE"
            if lift > 0.02
            else "no lift over best component (relabelling, not fusion)"
        )
        print(f"\n  {name}")
        print(f"    why: {why}")
        print(f"    members: {', '.join(members)}")
        print(
            f"    composite IC {cic:+.4f} | best single |IC| {best_single:.4f} | lift {lift:+.4f}"
        )
        print(
            f"    same-period {(r.get('same_period_corr') or 0):+.3f} | "
            f"resid {(r.get('residual_ic') or 0):+.4f} | "
            f"revSh {(r.get('sharpe_reversal') or 0):+.2f} | {r.get('verdict')}"
        )
        print(f"    -> {verdict}")
        out.append(
            {
                "combo": name,
                "members": members,
                "ic": cic,
                "best_single": round(best_single, 4),
                "lift": round(lift, 4),
                "verdict": r.get("verdict"),
                "fusion_verdict": verdict,
            }
        )

    Path("data/fusion_engine.json").write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "n_combos": n_tests,
                "bonferroni_alpha": 0.05 / n_tests,
                "components": {k: round(v, 4) for k, v in base.items()},
                "results": out,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(
        f"\n=> {sum(1 for o in out if 'ADDS VALUE' in o['fusion_verdict'])}/{n_tests} "
        f"combinations beat their best component."
    )


if __name__ == "__main__":
    main()
