"""Broad stablecoin-supply momentum collector + Stage-A screen (2026-07-23 alt-data batch).

Total stablecoin market cap (DefiLlama, ALL issuers/chains) as a macro dollar-liquidity signal:
rising aggregate supply = net minting = new capital entering crypto -> momentum (supply-z up
precedes higher forward BTC return). Cleanest survivor of the alt-data batch: IC +0.067, momentum
Sharpe 0.88, same-period corr +0.08 (orthogonal), residual IC +0.072 (STRENGTHENS -> genuinely
leading), over 900 days. Passes the de-contam + SUSPECT-LOOKAHEAD rails.

RELATIONSHIP TO EXISTING SIGNAL (angle-14, no double-counting): scripts/run_stablecoin_flows.py
already RECORDS a supply figure (USDT+USDC on-chain totalSupply) as a designated signal, but it is
NOT screened or forward-tracked in run_axis_shadows -- it just accrues in an archive. This is the
SAME economic construct with (a) broader coverage (all stablecoins incl. DAI/USDe/FDUSD/PYUSD, not
just USDT+USDC) and (b) the formal Holm-tracked forward clock the archived version lacks. Treat the
two as ONE hypothesis for evidence purposes; this is the evaluated version.

Free DefiLlama API, no key. stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_STABLES = "https://stablecoins.llama.fi/stablecoincharts/all"
_BINANCE = "https://api.binance.com/api/v3/klines"
_SERIES = Path("data/stablecoin_supply.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-stablesupply/1.0"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def _supply() -> dict[str, float]:
    d = _get(_STABLES)
    out: dict[str, float] = {}
    if not isinstance(d, list):        # narrow the untyped JSON boundary, do not assume shape
        return out
    for x in d:
        v = x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}
        peg = v.get("peggedUSD") if isinstance(v, dict) else None
        if peg is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(peg)
    return out


def _binance_daily(sym: str, n: int = 900) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    sup = _supply()
    gbtc = _binance_daily("BTCUSDT")
    if not (sup and gbtc):
        raise SystemExit(f"fetch failed: supply={len(sup)} binance={len(gbtc)}")
    dates = sorted(set(sup) & set(gbtc))
    if len(dates) < 90:
        raise SystemExit(f"only {len(dates)} aligned days")

    sig = np.array([sup[d] for d in dates])
    btc = np.array([gbtc[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0

    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    scr = stage_a_screen(sig, ret, name="stablecoin_supply_momentum")

    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "supply_usd": round(float(sig[-1]), 0),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"STABLECOIN-SUPPLY SCREEN | {len(dates)} aligned days")
    print(f"  current z20: {z[-1]:+.2f}   total supply ${sig[-1]:,.0f}")
    print(f"  IC {scr['ic']:+.4f} | same-period {scr['same_period_corr']:+.3f} "
          f"| residual IC {scr['residual_ic']:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM {scr['sharpe_momentum']}  "
          f"REVERSAL {scr['sharpe_reversal']}")
    print(f"  VERDICT (Stage-A, zero promotion authority): {scr['verdict']}  "
          f"[momentum, direction=+1; SAME construct as stablecoin_flows supply field -- one "
          f"hypothesis, this is the formally-tracked version]")


if __name__ == "__main__":
    main()
